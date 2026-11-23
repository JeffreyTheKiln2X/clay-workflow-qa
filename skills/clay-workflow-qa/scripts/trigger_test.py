#!/usr/bin/env python3
"""Step d of the ladder: the trigger test. One test record joins the test copy's trigger segment; the on enter
trigger starts the copy; the run is read back; the record is deleted. Free, except the run itself (each paid step
on its path; usually 0 with test people).

  python3 skills/clay-workflow-qa/scripts/trigger_test.py make <target> <spec.json>   # the helper and the record
  python3 skills/clay-workflow-qa/scripts/trigger_test.py where <target>              # which segments hold it
  python3 skills/clay-workflow-qa/scripts/trigger_test.py enter <target>              # rename it into the copy's (t)
  python3 skills/clay-workflow-qa/scripts/trigger_test.py watch <target> [minutes]    # one bounded wait, max 10
  python3 skills/clay-workflow-qa/scripts/trigger_test.py readback <target>           # the run, the fields, (t)
  python3 skills/clay-workflow-qa/scripts/trigger_test.py gone <target>               # after the delete in the app

The record is made named "PENDING <tag> <label>", so no segment with the copy's name clause holds it. `enter`
renames it "TEST <tag> <label>": that rename is the entry. `where` must show it in no live trigger segment, before
and after `enter`, or the live play would run it. A spec keeps it out of the live play by a live field the copy
does not read (for a play with a status, give the live status `out` with a TEST reason: the copy reads the
stand-in status).

The spec (JSON, kept beside the report in <target folder>/tests/):
  {"entity": "companies" or "people", "label": "<what it tests>", "lookup": "domain" or "email",
   "record": {"<field id or system key>": value, ...},
   "people": [{"email": ..., "first_name": ..., "last_name": ..., "title": ..., "<field id>": value}, ...]}
`people` is for a company record: each person is linked to it. Records are deleted in the Clay app (no CLI
deletes a record): people first, then the company. `gone` reads them back.
"""
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp  # noqa: E402

CODE = {"companies": "ACCOUNT", "people": "CONTACT"}
NAME = {"companies": "org_name", "people": "name"}
PATH = {"companies": "account_entity_field_values", "people": "contact_entity_field_values"}


def upsert_node(name, entity, keys, lookup, link=False):
    m = {"entityType": {"type": "static", "value": CODE[entity]},
         "recordFields|removeNullValues": {"type": "static", "value": True},
         "recordFields|selectedRecordFields": {"type": "static", "value": list(keys)},
         "lookupFields|selectedLookupFields": {"type": "static", "value": [lookup]},
         "lookupFields|" + lookup: {"type": "reference", "expression": "{{%s}}" % lookup}}
    props = {"entityType": {"type": "string"}}
    for k in keys:
        m["recordFields|" + k] = {"type": "reference", "expression": "{{%s}}" % k}
        props[k] = {"type": "string"}
    props[lookup] = {"type": "string"}
    if link:
        m["associations|accountId"] = {"type": "reference", "expression": "{{company_id}}"}
        props["company_id"] = {"type": "string"}
    return {"nodeType": "tool", "name": name, "description": "clay-workflow-qa helper: makes TEST records. Delete after.",
            "tools": [{"toolType": "clay_action", "actionKey": "upsert-audiences-record", "actionPackageId": tp.AUD,
                       "description": "Create or update Audiences record", "inputMappingConfig": m}],
            "inputSchema": {"type": "object", "required": ["entityType"], "properties": props}, "incomingEdges": []}


def strs(d):
    return {k: v if isinstance(v, str) else json.dumps(v) for k, v in d.items()}


def ctx(play):
    s = tp.load_state(play)
    c = s.get("copy") or sys.exit("FAIL: no test copy in today's state (test_copy.py make)")
    t = list((c.get("triggers") or {}).values())
    if not t:
        sys.exit("FAIL: the copy has no segment trigger")
    return s, c, t[0]


def make(play, spec_path):
    s, c, t = ctx(play)
    spec = json.load(open(spec_path))
    ent, tag = spec["entity"], c["tag"]
    tt = s.setdefault("trigger_test", {"spec": spec_path})
    rec = dict(spec["record"], **{NAME[ent]: "PENDING %s %s" % (tag, spec["label"])})
    if not tt.get("wf"):
        tt["wf"] = tp.clay("workflows", "create", "--name", "TEST %s helper: make trigger test records (delete after)"
                           % tag)["id"]
        tp.save_state(play, s)
    if not tt.get("rec_node"):
        keys = [k for k in rec if k != spec["lookup"]]
        tt["rec_node"] = tp.clay("workflows", "nodes", "create", tt["wf"], inp=upsert_node(
            "Make the TEST record", ent, keys, spec["lookup"]))["nodeId"]
        tp.save_state(play, s)
    if not tt.get("record_id"):
        out, run, st = tp.node_test(tt["wf"], tt["rec_node"], strs(rec))
        rid = (out.get("result") or {}).get("entityId")
        if not rid:
            sys.exit("FAIL: the record was not made (%s %s): %s" % (run, st, json.dumps(out)[:600]))
        tt["record_id"] = rid
        tp.save_state(play, s)
        print("record", ent, rid, rec[NAME[ent]])
    if spec.get("people"):
        keys = sorted({k for p in spec["people"] for k in p if k != "email"} | {"name"})
        if not tt.get("pe_node"):
            tt["pe_node"] = tp.clay("workflows", "nodes", "create", tt["wf"], inp=upsert_node(
                "Make a TEST person", "people", keys, "email", link=True))["nodeId"]
            tp.save_state(play, s)
        tt.setdefault("people", {})
        for p in spec["people"]:
            if p["email"] in tt["people"]:
                continue
            row = dict({k: "" for k in keys}, **p, name="TEST %s %s %s" % (tag, p.get("first_name", ""),
                                                                           p.get("last_name", "")),
                       company_id=str(tt["record_id"]))
            out, run, st = tp.node_test(tt["wf"], tt["pe_node"], strs(row))
            pid = (out.get("result") or {}).get("entityId")
            if not pid:
                sys.exit("FAIL: person %s was not made (%s %s): %s" % (p["email"], run, st, json.dumps(out)[:600]))
            tt["people"][p["email"]] = pid
            tp.save_state(play, s)
            print("person", p["email"], pid)
    where(play)


def with_name(flt, ent, prefix):
    return {"type": "GroupOp", "combinationMode": "And", "items": [flt, {
        "type": "BinOp", "key": NAME[ent], "dataPath": [PATH[ent], "field", NAME[ent]], "operator": "StartsWith",
        "value": prefix, "entityType": CODE[ent]}]}


def where(play):
    """Count the test records in every live trigger segment and in the copy's trigger segment. Free."""
    s, c, t = ctx(play)
    tt, tag = s["trigger_test"], c["tag"]
    rows, bad = [], 0
    seen = set()
    for tr in tp.clay("workflows", "triggers", "list", "--scope", "live").get("data") or []:
        seg = (tr.get("settings") or {}).get("segmentId")
        # the copy's own segment is the target, not a live play: counted apart below
        if not seg or seg in seen or seg == t["segment"] or tr.get("status") not in (None, "live", "active", "enabled"):
            continue
        seen.add(seg)
        info = tp.unwrap(tp.clay("audiences", "get", seg, ok_fail=True))
        if "_error" in info:
            continue
        ent = info.get("entityType") or "people"
        n = 0
        for prefix in ("PENDING %s" % tag, "TEST %s" % tag):
            n += tp.clay("audiences", "records", "search-count", "--entity-type", ent,
                         inp=with_name(info["filter"], ent, prefix), flag="--filter")["count"]
        rows.append((seg, info["name"], ent, n))
        bad += n > 0
    mine = tp.unwrap(tp.clay("audiences", "get", t["segment"]))
    inside = tp.clay("audiences", "records", "search-count", "--entity-type", t["entity"],
                     inp=mine["filter"], flag="--filter")["count"]
    # the copy's filter with the PENDING name: 1 means every other clause admits the record, so the rename enters it
    ready = tp.clay("audiences", "records", "search-count", "--entity-type", t["entity"], flag="--filter",
                    inp=json.loads(json.dumps(mine["filter"]).replace('"TEST %s"' % tag, '"PENDING %s"' % tag)))["count"]
    print("ready to enter (the copy's filter with the PENDING name): %d" % ready)
    for seg, name, ent, n in rows:
        if n:
            print("FAIL live trigger segment %s %r (%s) holds %d test record(s): the live play would run it"
                  % (seg, name, ent, n))
    print("%s: %d live trigger segments checked, %d hold a test record; the copy's %r holds %d" % (
        "FAIL" if bad else "PASS", len(rows), bad, mine["name"], inside))
    tt.setdefault("where", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                       "live_hits": bad, "copy_t": inside, "checked": len(rows)})
    tp.save_state(play, s)
    return 1 if bad else 0


def enter(play):
    s, c, t = ctx(play)
    tt = s["trigger_test"]
    spec = json.load(open(tt["spec"]))
    ent = spec["entity"]
    rec = dict(spec["record"], **{NAME[ent]: "TEST %s %s" % (c["tag"], spec["label"])})
    if where(play):
        sys.exit("STOP: a live trigger segment holds the record; nothing renamed")
    out, run, st = tp.node_test(tt["wf"], tt["rec_node"], strs(rec))
    tt["entered_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    tp.save_state(play, s)
    print("entered", tt["entered_at"], run, st)
    return where(play)


def runs(c):
    return tp.clay("workflows", "runs", "list", c["wf"], "--limit", "20").get("data") or []


def watch(play, minutes):
    s, c, t = ctx(play)
    tt = s["trigger_test"]
    end = time.time() + 60 * min(minutes, 10)
    while True:
        hits = [r for r in runs(c) if r.get("trigger") and (r.get("createdAt") or "") >= tt["entered_at"]]
        if hits:
            tt["trigger_runs"] = [{k: r.get(k) for k in ("runId", "status", "createdAt")} for r in hits]
            tp.save_state(play, s)
            print("FIRED", json.dumps(tt["trigger_runs"], default=str))
            return 0
        if time.time() > end:
            break
        time.sleep(50)
    waited = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.datetime.fromisoformat(tt["entered_at"])).total_seconds() / 60
    print("no trigger run yet: %.0f minutes since the entry (bar: 90)" % waited)
    return 1


def readback(play):
    s, c, t = ctx(play)
    tt = s["trigger_test"]
    spec = json.load(open(tt["spec"]))
    stand = {v["id"]: v for v in (c.get("fields") or {}).values()}
    rec = tp.clay("audiences", "records", "get", "--entity-type", spec["entity"], "--ids", str(tt["record_id"]))["data"][0]
    out = {"record": {v["name"]: rec["fields"].get(k) for k, v in stand.items() if v["entity"] == spec["entity"]}}
    pids = [str(v) for v in (tt.get("people") or {}).values()]
    if pids:
        out["people"] = {str(p["recordId"]): {v["name"]: p["fields"].get(k) for k, v in stand.items()
                                              if v["entity"] == "people" and p["fields"].get(k) is not None}
                         for p in tp.clay("audiences", "records", "get", "--entity-type", "people", "--ids",
                                          ",".join(pids))["data"]}
    mine = tp.unwrap(tp.clay("audiences", "get", t["segment"]))
    out["in_copy_t"] = tp.clay("audiences", "records", "search-count", "--entity-type", t["entity"],
                               inp=mine["filter"], flag="--filter")["count"]
    rr = [r for r in runs(c) if (r.get("createdAt") or "") >= tt.get("entered_at", "~")]
    out["runs"] = []
    for r in rr:
        st = tp.clay("workflows", "runs", "get", r["runId"])
        out["runs"].append({"run": r["runId"], "by_trigger": bool(r.get("trigger")), "status": st.get("status"),
                            "created": r.get("createdAt"), "data": st.get("dataCreditsUsed"),
                            "action": st.get("actionCreditsUsed")})
    tt["readback"] = out
    tp.save_state(play, s)
    print(json.dumps(out, indent=1, default=str))


def gone(play):
    s, c, t = ctx(play)
    tt = s["trigger_test"]
    spec = json.load(open(tt["spec"]))
    left = tp.clay("audiences", "records", "get", "--entity-type", spec["entity"], "--ids", str(tt["record_id"]),
                   ok_fail=True).get("data") or []
    pids = [str(v) for v in (tt.get("people") or {}).values()]
    lp = (tp.clay("audiences", "records", "get", "--entity-type", "people", "--ids", ",".join(pids),
                  ok_fail=True).get("data") or []) if pids else []
    if tt.get("wf"):
        tp.clay("workflows", "delete", tt["wf"], ok_fail=True)
        h = tp.clay("workflows", "get", tt["wf"], ok_fail=True)
        print("helper", tt["wf"], "gone" if "_error" in h else "STILL THERE")
    print("%s: %d record and %d people left" % ("PASS" if not left and not lp else "FAIL", len(left), len(lp)))
    tt["gone"] = not left and not lp
    tp.save_state(play, s)
    return 0 if tt["gone"] else 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, play = sys.argv[1], sys.argv[2]
    if cmd == "make":
        make(play, sys.argv[3])
        return 0
    if cmd == "watch":
        return watch(play, int(sys.argv[3]) if len(sys.argv) > 3 else 9)
    fn = {"where": where, "enter": enter, "readback": readback, "gone": gone}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return fn(play) or 0


if __name__ == "__main__":
    sys.exit(main())
