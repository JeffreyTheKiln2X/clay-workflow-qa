#!/usr/bin/env python3
"""Step a of the ladder: the static check. Free: repo checks and Clay reads only, no run, 0 credits.

  python3 skills/clay-workflow-qa/scripts/static_check.py <target> [--targets FILE]   # one target of the targets file
  python3 skills/clay-workflow-qa/scripts/static_check.py <target> --json F          # also write every row to F
  python3 skills/clay-workflow-qa/scripts/static_check.py <target> --filters         # also print each segment filter,
                                                                                    # one clause a line, to compare
                                                                                    # with the doc

Each row is PASS, WARN, FAIL or INFO with its proof. Exit 1 on any FAIL.

  repo      each command in the entry's `repo_checks:` passes (none listed: INFO)
  name      each live part's name in Clay equals its name in the targets file; no live part keeps "TEST "
            (unless stage: test)
  publish   each live workflow has a published version; the draft code equals the published code
  trigger   each trigger is bound to the newest published version and to a segment of this target; its
            status (live or paused)
  settings  the first step after each trigger is a Settings step with a dry run switch; its value in the
            published code (on: the workflow writes nothing outside Clay; off: it is live). No Settings step
            or no switch: WARN, the switch is unverified and every write counts as live (FAIL under
            convention: ior_t)

Only with `convention: ior_t` in the entry (the input, review, output and trigger segment convention):

  segments  one (i), one (r), one (o); one (t) only when a segment trigger reads it (a scheduled
            recheck on (r) is not one); the trigger segment is a (t), never (i); (r) filters status = review;
            (o) filters one status value (the success status)
  status    the three status columns <x>_status, <x>_status_at, <x>_status_reason are in the targets file

Without it, each listed segment is checked to exist and to carry its listed name, and the convention rows
print one INFO line.

Run from the project root after `clay whoami` names the right workspace.
"""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp  # noqa: E402

ROWS = []
DRY = re.compile(r"^\s*(DRY_RUN|dry_run|DRY|dry)\s*=\s*(True|False|\"?true\"?|\"?false\"?)", re.M)
KIND = re.compile(r"^(TEST |SUNSET: |ZZ DELETE: )*\((i|r|o|t)\) ")


def row(level, check, text):
    ROWS.append({"level": level, "check": check, "text": text})
    print("%-4s %-9s %s" % (level, check, text))


def repo(play, block):
    cmds = block.get("repo_checks") or []
    if not cmds:
        row("INFO", "repo", "no repo_checks listed in the targets file entry: nothing run")
    for line in cmds:
        cmd = shlex.split(line.replace("{target}", play))
        r = subprocess.run(cmd, capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or [r.stderr.strip()])[-1]
        row("PASS" if r.returncode == 0 else "FAIL", "repo", "%s: %s" % (" ".join(cmd), last))


def code_of(nodes, key):
    return {n["id"]: (n.get(key) or {}).get("code") if key == "currentScriptVersion" else n.get("code")
            for n in nodes if n.get("nodeType") == "code"}


def workflows(block, test_stage, conv):
    live = {k: v for k, v in ((block.get("clay_ids") or {}).get("workflows") or {}).items() if not tp.retired(v)}
    segs = (block.get("clay_ids") or {}).get("segments") or {}
    found = {"segment_triggers": set(), "dry": {}}
    for wf, name in live.items():
        info = tp.clay("workflows", "get", wf, ok_fail=True)
        if "_error" in info:
            row("FAIL", "name", "%s %s: not in Clay (%s)" % (wf, name, info["_error"][:120]))
            continue
        cname = info.get("name", "")
        row("PASS" if cname == name else "FAIL", "name", "workflow %s: Clay %r, targets file %r" % (wf, cname, name))
        if cname.startswith("TEST ") and not test_stage:
            row("FAIL", "name", "workflow %s is live and keeps a TEST name" % wf)
        vers = tp.clay("workflows", "versions", "list", wf).get("data") or []
        if not vers:
            row("WARN", "publish", "%s: never published, so no trigger fires (a TEST draft is fine)" % cname)
            newest = None
        else:
            newest = vers[0]["id"]
            row("PASS", "publish", "%s: newest version %s, %s" % (cname, newest, vers[0].get("publishedAt", "")[:10]))
            draft = tp.clay("workflows", "graph", "get", wf, "--mode", "full")["nodes"]
            snap = tp.clay("workflows", "snapshots", "get", wf, newest)["nodes"]
            d, s = code_of(draft, "code"), code_of(snap, "currentScriptVersion")
            diff = sorted(k for k in set(d) | set(s) if (d.get(k) or "").strip() != (s.get(k) or "").strip())
            names = {n["id"]: n["name"] for n in draft + snap}
            row("PASS" if not diff and len(draft) == len(snap) else "WARN", "publish",
                "%s: draft equals published" % cname if not diff and len(draft) == len(snap) else
                "%s: draft differs from published (%d vs %d steps; code differs in %s). A publish ships these; "
                "a test copy of the draft tests them, not the live play" % (cname, len(draft), len(snap),
                                                                             ", ".join(names.get(k, k) for k in diff) or "none"))
        trig = tp.clay("workflows", "triggers", "list", "--workflow-id", wf, "--scope", "live" if newest else "draft")
        graph = tp.clay("workflows", "graph", "get", wf, "--mode", "full")["nodes"]
        by_id = {n["id"]: n for n in graph}
        for t in trig.get("data") or []:
            st = t.get("settings") or {}
            full = tp.clay("workflows", "triggers", "get", t["id"])
            bound = full.get("snapshotId")
            seg = st.get("segmentId") or full.get("segmentId")
            label = "%s trigger %s (%s, %s)" % (cname, t["id"][:8], t.get("triggerType") or st.get("triggerType"),
                                                t.get("status"))
            if newest:
                row("PASS" if bound == newest else "FAIL", "trigger",
                    "%s: bound to %s, newest published %s" % (label, bound, newest))
            if seg:
                sname = segs.get(seg, "")
                kind = (KIND.match(sname) or [None, None, None])[2] if conv else None
                ttype = t.get("triggerType") or st.get("triggerType") or full.get("triggerType")
                # a scheduled recheck on (r) is not an entry trigger: it makes no (t)
                if ttype == "audience_scheduled" and kind == "r":
                    row("PASS", "trigger", "%s reads %r: a scheduled recheck of the review segment" % (label, sname))
                    seg = None
                else:
                    found["segment_triggers"].add(seg)
            if seg:
                if not sname:
                    row("FAIL", "trigger", "%s reads segment %s, which is not this target's" % (label, seg))
                elif kind == "i":
                    row("FAIL", "trigger", "%s reads the input segment %r: it runs every record" % (label, sname))
                else:
                    row("PASS" if kind == "t" or not conv else "WARN", "trigger", "%s reads %r" % (label, sname))
            # the Settings step: the first step after the trigger node
            tnode = full.get("workflowNodeId")
            nxt = [e["targetNode"] for e in (by_id.get(tnode) or {}).get("outgoingEdges") or []]
            first = by_id.get(nxt[0]) if nxt else None
            if not first or "settings" not in first.get("name", "").lower():
                row("FAIL" if conv else "WARN", "settings", "%s: the first step is %r, not a Settings step: "
                    "the write switch is unverified, count every write as live" % (label, first and first.get("name")))
                continue
            src = first.get("code") or ""
            if newest:
                snapnode = tp.clay("workflows", "snapshots", "get", wf, newest, "--node-id", first["id"])
                ns = snapnode.get("nodes") or [snapnode]
                src = ((ns[0].get("currentScriptVersion") or {}).get("code")) or src
            m = DRY.search(src)
            if not m:
                row("FAIL" if conv else "WARN", "settings", "%s: %r has no dry run switch: the write switch is "
                    "unverified, count every write as live" % (label, first["name"]))
                continue
            on = m.group(2).strip('"').lower() == "true"
            found["dry"][wf] = on
            row("PASS", "settings", "%s: %r %s = %s in the %s code: dry run %s" % (
                label, first["name"], m.group(1), m.group(2), "published" if newest else "draft", "ON" if on else
                "OFF (live: steps c and d need a test copy)"))
    return found


NAMES = {}


def field_names(entity):
    if entity not in NAMES:
        NAMES[entity] = {f["id"]: f["name"] for f in tp.clay("audiences", "fields", "list", "--entity-type", entity)["data"]}
    return NAMES[entity]


def plain(node, names, depth=0):
    """A segment filter in plain lines: one clause a line, groups indented."""
    pad = "    " * depth
    if node.get("type") == "GroupOp":
        out = ["%s%s of:" % (pad, "ALL" if node.get("combinationMode") == "And" else "ANY")]
        for it in node.get("items") or []:
            out += plain(it, names, depth + 1)
        return out
    key = node.get("key") or (node.get("dataPath") or ["?"])[-1]
    val = node.get("value")
    return ["%s%s %s%s" % (pad, names.get(key, key), node.get("operator"), "" if val is None else " %r" % (val,))]


def segments(block, found, test_stage, conv):
    segs = {k: v for k, v in ((block.get("clay_ids") or {}).get("segments") or {}).items() if not tp.retired(v)}
    fields = (block.get("clay_ids") or {}).get("fields") or {}
    kinds = {}
    for sid, name in segs.items():
        kind = (KIND.match(name) or [None, None, None])[2] if conv else None
        if conv and not kind:
            continue                     # a pool or helper segment the target reads; not one of its own
        info = tp.unwrap(tp.clay("audiences", "get", sid, ok_fail=True))
        if "_error" in info:
            row("FAIL", "segments", "%s %r: not in Clay" % (sid, name))
            continue
        kinds.setdefault(kind, []).append((sid, info))
        if "--filters" in sys.argv:
            print("\n".join(["     filter of %r:" % name] + ["       " + ln for ln in plain(
                info.get("filter") or {}, field_names(info.get("entityType") or "people"))]))
        row("PASS" if info["name"] == name else "FAIL", "name", "segment %s: Clay %r, targets file %r" % (sid, info["name"], name))
        if info["name"].startswith("TEST ") and not test_stage:
            row("FAIL", "name", "segment %s is live and keeps a TEST name" % sid)
        if kind in ("r", "o"):
            items = (info.get("filter") or {}).get("items") or []
            eq = [i for i in items if i.get("operator") == "Equal" and "status" in fields.get(i.get("key"), "")]
            val = eq[0].get("value") if eq else None
            good = len(items) == 1 and eq and (kind == "o" or val == "review")
            row("PASS" if good else "WARN", "segments", "(%s) %r filters %s" % (
                kind, info["name"], "%s = %r" % (fields.get(eq[0]["key"]), val) if eq else
                "%d clauses and no single status value" % len(items)))
    if not conv:
        row("INFO", "segments", "no `convention: ior_t` in the entry: the (i)/(r)/(o)/(t) and status column checks are skipped")
        return
    for k in ("i", "r", "o"):
        n = len(kinds.get(k, []))
        row("PASS" if n == 1 else "FAIL", "segments", "(%s): %d segment%s" % (k, n, "" if n == 1 else "s"))
    t = kinds.get("t", [])
    want = bool(found["segment_triggers"])
    row("PASS" if len(t) == (1 if want else 0) else "FAIL", "segments",
        "(t): %d segment(s); %s" % (len(t), "a field target: one (t) read by its trigger" if want else
                                    "a signal target: no (t)"))
    st = [n for n in fields.values() if re.search(r"_status(_at|_reason)?$", n.split("#")[0].strip())]
    row("PASS" if len(st) >= 3 else "FAIL", "status", "status columns in the targets file: %s" % (", ".join(st) or "none"))


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print(__doc__)
        return 2
    play = sys.argv[1]
    block = tp.play_block(play)
    test_stage = block.get("stage") == "test"
    conv = block.get("convention") == "ior_t"
    print("Static check: %s (%s), stage %s" % (block.get("name"), play, block.get("stage", "live")))
    repo(play, block)
    found = workflows(block, test_stage, conv)
    segments(block, found, test_stage, conv)
    fails = sum(r["level"] == "FAIL" for r in ROWS)
    warns = sum(r["level"] == "WARN" for r in ROWS)
    infos = sum(r["level"] == "INFO" for r in ROWS)
    print("Static check %s: %d fail, %d warn, %d info, %d pass" % (
        "FAIL" if fails else "PASS", fails, warns, infos, len(ROWS) - fails - warns - infos))
    if "--json" in sys.argv:
        json.dump({"rows": ROWS, "dry_run": found["dry"]}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
