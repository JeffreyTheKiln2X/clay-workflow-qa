#!/usr/bin/env python3
"""A test copy of a live workflow, so steps c and d never touch the live one. 0 credits to make.

  python3 skills/clay-workflow-qa/scripts/test_copy.py make <target> <workflow id> --tag <tag> [--sub OLD NEW]...
          [--sub-code OLD NEW]...   # a text swap in every code step: code that reads a written field by name
          [--echo-writes [--keep-write <step name>]...]   # write steps become code steps that write nothing
          [--draft]   # copy the draft although it differs from the published version: the owner asked to test
                      # an unpublished rebuild (a new draft of a live workflow)
  python3 skills/clay-workflow-qa/scripts/test_copy.py check <target>      # read the copy back: dry run on, writes
  python3 skills/clay-workflow-qa/scripts/test_copy.py publish <target>    # publish the copy (test mode, dry run on)
  python3 skills/clay-workflow-qa/scripts/test_copy.py delete <target>     # pause and delete the copy, its trigger
                                                                         # segment and its stand-in fields

What `make` builds, all named "TEST <tag> ...":

- The copy: every step of the live workflow's draft (stop first when the draft differs from the published version:
  static_check.py says so), the same functions called by id, the same code.
- Dry run on: the Settings step's switch is set to True (`DRY_RUN = False` -> `DRY_RUN = True`; --sub adds other
  text swaps in the Settings code). `check` fails when the published copy's Settings step is not in dry run.
- Stand-in fields: every Audiences field a write step of the copy names (update or upsert Audiences record) gets a
  stand-in field "TEST <tag> <name>", and the copy writes the stand-in. So a run on a real record changes no live
  field, and no live segment moves.
- With --echo-writes (when stand-ins cannot be made, for example at Clay's cap of 100 text fields per entity): each
  Audiences write step becomes a code step of the same name, inputs and edges that writes nothing and returns
  "would_set <field>" for each field. A step named by --keep-write keeps the write, to a stand-in field.
- A manual trigger for each live trigger with no segment (a signal: Clay allows one trigger per signal), with the
  live trigger's top level outputs, so a hand run enters the copy as the signal hands a record.
- A trigger segment, only when the live workflow has a segment trigger: the live (t) filter, with the stand-in
  fields swapped in (so a run moves the record out of it), plus "name starts with TEST <tag>" (so no real record
  can start the copy). One on enter trigger on it, of the same entity.

The copy is never published by `make`. A publish of a TEST copy with dry run on and the send switch off is a test
mode publish (the play builder's "What needs a yes" names who decides). State: <target folder>/tests/<date>-state.json.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp  # noqa: E402

KEEP = ("name", "description", "nodeType", "code", "conditionalMode", "rulesConditionalConfig", "listMode",
        "listFailureMode", "listEntriesRef", "subworkflowId", "delay", "delayUnit", "agentClaygentId", "inputSchema")
DRY_FALSE = re.compile(r"^(\s*)(DRY_RUN|dry_run)(\s*=\s*)False\b", re.M)
ENTITY = {"ACCOUNT": "companies", "CONTACT": "people"}
NAME_FIELD = {"ACCOUNT": "org_name", "CONTACT": "name"}
PATH = {"ACCOUNT": "account_entity_field_values", "CONTACT": "contact_entity_field_values"}


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def subs(flag="--sub"):
    out, i = [], 0
    while flag in sys.argv[i:]:
        j = sys.argv.index(flag, i)
        out.append((sys.argv[j + 1], sys.argv[j + 2]))
        i = j + 3
    return out


def write_fields(nodes):
    """{field id: entity} of every Audiences field a write step names."""
    out = {}
    for n in nodes:
        for t in n.get("tools") or []:
            if t.get("actionKey") not in tp.WRITE_ACTIONS:
                continue
            m = t.get("inputMappingConfig") or {}
            ent = ((m.get("entityType") or {}).get("value")) or "CONTACT"
            for k in m:
                if k.startswith("recordFields|audf_"):
                    out[k.split("|", 1)[1]] = ENTITY.get(ent, "people")
    return out


def echoed(n):
    """True when --echo-writes turns this write step into a code step that writes nothing."""
    keep = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--keep-write" and i + 1 < len(sys.argv)]
    return ("--echo-writes" in sys.argv and n["name"] not in keep and
            any(t.get("actionKey") in tp.WRITE_ACTIONS for t in n.get("tools") or []))


ECHO = ('''# TEST copy (clay-workflow-qa --echo-writes): the live step writes Audiences. This copy writes nothing and shows what
# the live step would set, field by field.
FIELDS = %s


def handler(context):
    out = {"test_copy": "no Audiences write"}
    for name, key in FIELDS.items():
        try:
            v = context.get_input(key)
        except Exception:
            v = None
        out["would_set " + name] = "" if v is None else (v if isinstance(v, str) else json.dumps(v, default=str))
    return out
''')


def echo_spec(n, names):
    """A code step with the write step's name, inputs and edges, that returns what it would write."""
    t = [t for t in n["tools"] if t.get("actionKey") in tp.WRITE_ACTIONS][0]
    m = t.get("inputMappingConfig") or {}
    ent = ENTITY.get(((m.get("entityType") or {}).get("value")) or "CONTACT", "people")
    fields = {}
    for k, v in m.items():
        if k.startswith("recordFields|audf_"):
            key = re.sub(r"^\{\{\s*|\s*\}\}$", "", str((v or {}).get("expression") or ""))
            fid = k.split("|", 1)[1]
            fields[(names[ent].get(fid) or {}).get("name") or fid] = key
    props = {k: dict({"type": "string"}, **{kk: vv for kk, vv in v.items() if kk in ("type", "sourceNodeId", "sourcePath")})
             for k, v in ((n.get("inputSchema") or {}).get("properties") or {}).items()
             if isinstance(v, dict) and v.get("sourceNodeId")}
    return {"name": n["name"], "nodeType": "code",
            "description": "TEST copy: writes nothing; returns what the live step would write. " + (n.get("description") or ""),
            "code": "import json\n" + ECHO % json.dumps(fields, indent=1),
            "inputSchema": {"type": "object", "properties": props}}


def swap(obj, ids):
    s = json.dumps(obj)
    for old, new in ids.items():
        s = s.replace(old, new)
    return json.loads(s)


def order(nodes):
    """Nodes in an order where every source of an edge or an input exists before it."""
    done, out, left = set(), [], [n for n in nodes if n["nodeType"] != "trigger"]
    trig = {n["id"] for n in nodes if n["nodeType"] == "trigger"}
    while left:
        moved = False
        for n in list(left):
            srcs = {e["sourceNode"] for e in n.get("incomingEdges") or []}
            srcs |= {v["sourceNodeId"] for v in ((n.get("inputSchema") or {}).get("properties") or {}).values()
                     if isinstance(v, dict) and v.get("sourceNodeId")}
            if n.get("listEntriesRef"):
                srcs.add(n["listEntriesRef"]["sourceNodeId"])
            if srcs <= done | trig:
                out.append(n)
                done.add(n["id"])
                left.remove(n)
                moved = True
        if not moved:
            sys.exit("FAIL: a cycle or a missing source among %s" % [n["name"] for n in left])
    return out


def make(play, wf, tag):
    s = tp.load_state(play)
    if s.get("copy", {}).get("deleted"):          # a second test the same day: keep the first copy's record
        s.setdefault("earlier_copies", []).append(s.pop("copy"))
    if s.get("copy", {}).get("made"):
        sys.exit("STOP: today's state already holds a copy %s. Run `check`, or `delete` first." % s["copy"]["wf"])
    src = tp.clay("workflows", "get", wf)
    vers = tp.clay("workflows", "versions", "list", wf).get("data") or []
    draft = tp.clay("workflows", "graph", "get", wf, "--mode", "full")["nodes"]
    if vers:
        snap = tp.clay("workflows", "snapshots", "get", wf, vers[0]["id"])["nodes"]
        dc = {n["id"]: (n.get("code") or "").strip() for n in draft if n["nodeType"] == "code"}
        sc = {n["id"]: ((n.get("currentScriptVersion") or {}).get("code") or "").strip()
              for n in snap if n["nodeType"] == "code"}
        if (dc != sc or len(draft) != len(snap)) and "--draft" not in sys.argv:
            sys.exit("STOP: the draft of %s differs from its published version %s. A copy would test the draft, not "
                     "the live play. Ask the play's owner which to test." % (src["name"], vers[0]["id"]))
    c = s.setdefault("copy", {"source": wf, "source_name": src["name"], "tag": tag,
                               "source_version": vers[0]["id"] if vers else None})
    tp.save_state(play, s)

    # stand-in fields
    names = {}
    for ent in ("companies", "people"):
        names[ent] = {f["id"]: f for f in tp.clay("audiences", "fields", "list", "--entity-type", ent)["data"]}
    stand = c.setdefault("fields", {})
    for fid, ent in write_fields([n for n in draft if not echoed(n)]).items():
        if fid in stand:
            continue
        f = names[ent].get(fid)
        if not f:
            sys.exit("FAIL: write field %s is not a %s field" % (fid, ent))
        nm = "TEST %s %s" % (tag, f["name"])
        made = tp.clay("audiences", "fields", "create", "--entity-type", ent, "--name", nm, "--data-type",
                       f.get("dataType") or "text")
        if made.get("name") != nm:
            sys.exit("FAIL: Clay named the stand-in %r, not %r (%s): remove it by hand" % (made.get("name"), nm, made.get("id")))
        stand[fid] = {"id": made["id"], "name": nm, "of": f["name"], "entity": ent}
        tp.save_state(play, s)
        print("stand-in", ent, nm, made["id"])
    ids = {k: v["id"] for k, v in stand.items()}

    # the trigger segment and the trigger
    trig = [n for n in draft if n["nodeType"] == "trigger"]
    live_trig = (tp.clay("workflows", "triggers", "list", "--workflow-id", wf, "--scope", "live" if vers else "draft")
                 .get("data") or [])
    if not c.get("wf"):
        c["wf"] = tp.clay("workflows", "create", "--name", "TEST %s COPY: %s" % (tag, src["name"]))["id"]
        tp.save_state(play, s)
        tp.clay("workflows", "update", c["wf"], "--description",
                "TEST copy of %s (%s) for clay-workflow-qa, tag %s. Dry run on; every Audiences write goes to a TEST %s "
                "stand-in field; only records named TEST %s can start it. Delete after the test." %
                (src["name"], wf, tag, tag, tag))
        print("copy", c["wf"])
    nodemap = c.setdefault("nodes", {})
    for t in live_trig:
        st = t.get("settings") or {}
        seg = st.get("segmentId")
        if t["id"] in c.get("triggers", {}):
            continue
        live_node = tp.clay("workflows", "triggers", "get", t["id"]).get("workflowNodeId")
        if not seg:
            # A signal (or another trigger with no segment) cannot be shared: Clay allows one trigger per signal.
            # The copy gets a manual trigger with the same top level outputs, so a hand run (`runs test --inputs`)
            # enters there with the inputs the live trigger hands, and no live event can start the copy.
            out = (tp.clay("workflows", "triggers", "get", t["id"]).get("outputSchema") or {}).get("properties") or {}
            schema = {"type": "object", "properties": {k: {"type": (v or {}).get("type") or "object"}
                                                        for k, v in out.items()}}
            new = tp.clay("workflows", "triggers", "create", c["wf"], inp={"triggerType": "manual",
                                                                           "inputSchema": schema})
            tid = new.get("resourceId") or new.get("id")
            g = tp.clay("workflows", "triggers", "get", tid)
            c.setdefault("triggers", {})[t["id"]] = {"id": tid, "segment": None, "entity": None, "type": "manual",
                                                    "node": g.get("workflowNodeId"), "source_type": t.get("triggerType")}
            nodemap[live_node or [n["id"] for n in trig][0]] = g.get("workflowNodeId")
            tp.save_state(play, s)
            print("manual trigger", tid, "for the live", t.get("triggerType"), "trigger", t["id"][:8])
            continue
        info = tp.unwrap(tp.clay("audiences", "get", seg))
        ent = info.get("entityType") or "people"
        code = {"companies": "ACCOUNT", "people": "CONTACT"}[ent]
        flt = {"type": "GroupOp", "combinationMode": "And", "items": [
            swap(info["filter"], ids),
            {"type": "BinOp", "key": NAME_FIELD[code], "dataPath": [PATH[code], "field", NAME_FIELD[code]],
             "operator": "StartsWith", "value": "TEST %s" % tag, "entityType": code}]}
        made = tp.clay("audiences", "create", "--entity-type", ent, "--name", "TEST %s COPY %s" % (tag, info["name"]),
                       "--description", "Test copy of %s for clay-workflow-qa: the live filter with the stand-in fields, "
                       "and only records named TEST %s. Delete after the test." % (info["name"], tag), inp=flt, flag="--filter")
        made = tp.unwrap(made)
        new = tp.clay("workflows", "triggers", "create", c["wf"], inp={"triggerType": "audience_segment",
                                                                       "segmentId": made["id"], "entityType": code})
        tid = new.get("resourceId") or new.get("id")
        g = tp.clay("workflows", "triggers", "get", tid)
        c.setdefault("triggers", {})[t["id"]] = {"id": tid, "segment": made["id"], "segment_name": made["name"],
                                                "entity": ent, "node": g.get("workflowNodeId"), "source_segment": seg}
        nodemap[live_node or [n["id"] for n in trig][0]] = g.get("workflowNodeId")
        tp.save_state(play, s)
        print("trigger segment", made["id"], made["name"], "trigger", tid, g.get("status"))
    if trig and not any(k in nodemap for k in (n["id"] for n in trig)):
        sys.exit("FAIL: the live trigger %s is not a segment trigger. Copy it by hand, then run make again."
                 % [n["name"] for n in trig])

    # the steps
    for n in order(draft):
        if n["id"] in nodemap:
            continue
        spec = {k: n[k] for k in KEEP if k in n}
        if echoed(n):
            spec = echo_spec(n, names)
            c.setdefault("echoed", []).append(n["name"])
            print("echo step (writes nothing):", n["name"])
        elif n.get("tools"):
            spec["tools"] = [{k: v for k, v in t.items() if k not in ("toolId", "inputParameters")} for t in n["tools"]]
            if any(t.get("actionKey") in tp.WRITE_ACTIONS for t in n["tools"]):
                spec["tools"] = swap(spec["tools"], ids)
        if n["nodeType"] == "code" and "settings" in n["name"].lower():
            code, k = DRY_FALSE.subn(r"\1\2\3True", spec.get("code") or "")
            for old, newtxt in subs():
                code = code.replace(old, newtxt)
            spec["code"] = code
            c["settings_node_source"] = n["id"]
            print("settings: dry run False -> True in %d place(s)" % k)
        if n["nodeType"] == "code" and subs("--sub-code"):
            code = spec.get("code") or ""
            for old, newtxt in subs("--sub-code"):
                if old in code:
                    code = code.replace(old, newtxt)
                    print("code swap in %r: %r -> %r" % (n["name"], old, newtxt))
            spec["code"] = code
        spec = swap(spec, nodemap)                                  # inputs and list refs to the copy's ids
        spec["incomingEdges"] = [dict({kk: e[kk] for kk in ("ruleId", "isDefaultRoute") if kk in e},
                                      sourceNode=nodemap[e["sourceNode"]]) for e in n.get("incomingEdges") or []]
        new = tp.clay("workflows", "nodes", "create", c["wf"], inp=spec)["nodeId"]
        nodemap[n["id"]] = new
        tp.save_state(play, s)
    print(json.dumps(tp.clay("workflows", "graph", "validate", c["wf"]))[:600])
    c["made"] = True
    tp.save_state(play, s)
    check(play)


def check(play):
    s = tp.load_state(play)
    c = s.get("copy") or sys.exit("FAIL: no copy in today's state")
    nodes = tp.clay("workflows", "graph", "get", c["wf"], "--mode", "full")["nodes"]
    bad = []
    st = [n for n in nodes if n["nodeType"] == "code" and "settings" in n["name"].lower()]
    vers = tp.clay("workflows", "versions", "list", c["wf"]).get("data") or []
    for n in st:
        code = n.get("code") or ""
        if vers:
            snap = tp.clay("workflows", "snapshots", "get", c["wf"], vers[0]["id"], "--node-id", n["id"])
            ns = snap.get("nodes") or [snap]
            code = (ns[0].get("currentScriptVersion") or {}).get("code") or code
        if DRY_FALSE.search(code) or not re.search(r"^\s*(DRY_RUN|dry_run)\s*=\s*True\b", code, re.M):
            bad.append("%s: dry run is not on" % n["name"])
    if not st:
        bad.append("no Settings step")
    live_ids = set(c.get("fields") or {})
    for f, ent in write_fields(nodes).items():
        if f in live_ids or not any(v["id"] == f for v in (c.get("fields") or {}).values()):
            bad.append("a write step names %s field %s, not a stand-in" % (ent, f))
    src_n = len(tp.clay("workflows", "graph", "get", c["source"], "--mode", "full")["nodes"])
    if len(nodes) != src_n:
        bad.append("%d steps, the source has %d" % (len(nodes), src_n))
    for line in bad:
        print("FAIL copy", line)
    print("copy %s %s: %d steps, %d stand-in fields, %s, %s" % (
        c["wf"], "FAIL" if bad else "PASS", len(nodes), len(c.get("fields") or {}),
        "published %s" % vers[0]["id"] if vers else "never published", "dry run on" if not bad else "see above"))
    return 1 if bad else 0


def publish(play):
    s = tp.load_state(play)
    c = s["copy"]
    if check(play):
        sys.exit("STOP: the copy failed its check; nothing published")
    v = tp.clay("workflows", "publish", c["wf"], "--name", "clay-workflow-qa %s: dry run on, stand-in fields" % c["tag"])
    c["published"] = v.get("id") or v.get("snapshotId") or v
    tp.save_state(play, s)
    for t in (c.get("triggers") or {}).values():
        g = tp.clay("workflows", "triggers", "get", t["id"])
        print("trigger", t["id"], "bound to", g.get("snapshotId"))
    return check(play)


def delete(play):
    s = tp.load_state(play, arg("--day", tp.TODAY))
    c = s.get("copy") or sys.exit("FAIL: no copy in that day's state")
    for t in (c.get("triggers") or {}).values():
        tp.clay("workflows", "triggers", "delete", t["id"], ok_fail=True)
    if c.get("wf"):
        tp.clay("workflows", "delete", c["wf"], ok_fail=True)
        gone = tp.clay("workflows", "get", c["wf"], ok_fail=True)
        print("copy", c["wf"], "gone" if "_error" in gone else "STILL THERE")
    for t in (c.get("triggers") or {}).values():
        if not t.get("segment"):           # a manual trigger: no segment of its own
            continue
        tp.clay("audiences", "archive", t["segment"], ok_fail=True)
        gone = tp.clay("audiences", "get", t["segment"], ok_fail=True)
        print("segment", t["segment"], "gone" if "_error" in gone else "STILL THERE")
    ours = {t["segment"] for t in (c.get("triggers") or {}).values()}
    for f in (c.get("fields") or {}).values():
        users = tp.clay("audiences", "fields", "segments", f["id"], "--entity-type", f["entity"], ok_fail=True)
        other = [a for a in (users.get("data") or []) if a.get("id") not in ours]
        if other:      # a field delete rewrites every segment that filters on it
            print("field", f["id"], f["name"], "KEPT: read by", [a.get("name") for a in other])
            continue
        r = tp.clay("audiences", "fields", "delete", f["id"], "--entity-type", f["entity"], ok_fail=True)
        print("field", f["id"], f["name"], "deleted" if "_error" not in r else "NOT deleted: " + r["_error"][:200])
    c["deleted"] = True
    tp.save_state(play, s, arg("--day", tp.TODAY))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, play = sys.argv[1], sys.argv[2]
    if cmd == "make":
        if len(sys.argv) < 4 or not arg("--tag"):
            sys.exit("usage: make <target> <workflow id> --tag <tag>")
        make(play, sys.argv[3], arg("--tag"))
    elif cmd == "check":
        return check(play)
    elif cmd == "publish":
        return publish(play)
    elif cmd == "delete":
        delete(play)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
