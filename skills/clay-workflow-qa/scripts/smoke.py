#!/usr/bin/env python3
"""Step c of the ladder: the dry run smoke. Up to 5 real records through the test copy's draft, dry run on.
Spends credits: each paid step on the path (state the estimate first).

  python3 skills/clay-workflow-qa/scripts/smoke.py <target> <record id> [<record id> ...] [--targets FILE]
          [--sf-field NAME] [--sf-writer NAME] [--sf-org ALIAS] [--outreach] [--wf <workflow id>]

  --wf          run this workflow instead of the copy in today's state (a TEST draft that is never live)
  --sf-field    the record field that holds the Salesforce account id: read the account and its contacts back
                (optional plug-in: needs the `sf` CLI and an org alias, --sf-org or env QA_SF_ORG or `sf_org:` in
                the targets file entry; without them the readback is skipped, never a FAIL)
  --sf-writer   the Salesforce user name the workflow writes as (a change by it is a FAIL, any other a WARN)
  --approve     the operator said yes to this smoke by name: approve each approval request it raises
  --outreach    read each person's Outreach prospect back: a sequence state made since the run start is a FAIL
                (optional plug-in: needs `outreach_reader:` in the entry, or env QA_OUTREACH_READER, a python file
                with token() and get(path, token); without it the readback is skipped, never a FAIL)

For each record: the record (and a company's people) is read before and after; the run is started with the record
as the trigger hands it (fields by name, with "id"). Bars, each counted apart:

  run       the run ends completed; no step failed
  calls     every function call answered (completed)
  fields    no live field changed on the record or its people; only stand-in (TEST) fields changed. A deleted
            field whose old value was cleared is counted apart (deleted_cleared), not as a live change
  salesforce, outreach   nothing written since the run start (when asked and available)

Writes <target folder>/tests/<date>-smoke.json. Exit 1 on a FAIL. The file keeps the real outputs for the
operator view (the report's "What it did" table), because the copy's runs are gone after the cleanup:
`written` (each stand-in field the run set, with its value) and `outputs` (each step's output, cut to 1500
characters: the people picked, the would-do lines, the Slack text as it would post). The credits spent are
compared with the credit limit of the entry (env QA_CREDIT_LIMIT, default 20): above it, a STOP line.
"""
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp  # noqa: E402

# Clay's own record bookkeeping: it changes on every run that touches a record, workflow write or not
SYSTEM = {"updated_at", "Updated at", "updatedAt", "last_synced_at", "workflows", "Workflows",
          "external_source_sync_status_v3", "Sync status"}


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def names(ent):
    return {f["id"]: f["name"] for f in tp.clay("audiences", "fields", "list", "--entity-type", ent)["data"]}


def records(ent, ids):
    out = {}
    for i in range(0, len(ids), 100):
        for r in tp.clay("audiences", "records", "get", "--entity-type", ent, "--ids", ",".join(ids[i:i + 100]))["data"]:
            out[str(r["recordId"])] = r
    return out


def steps(wf, run_id):
    out, cursor = [], None
    while True:
        page = tp.clay("workflows", "runs", "steps", wf, run_id, *(["--cursor", cursor] if cursor else []))
        out += page.get("data") or []
        cursor = page.get("cursor") or page.get("nextCursor")
        if not cursor or not page.get("data"):
            return out


def diff(before, after, stand):
    changed = []
    for k in set(before) | set(after):
        if k in SYSTEM or json.dumps(before.get(k), sort_keys=True) == json.dumps(after.get(k), sort_keys=True):
            continue
        changed.append((k, k in stand))
    return changed


def sf_org(block):
    return arg("--sf-org") or os.environ.get("QA_SF_ORG") or block.get("sf_org")


def sf(org, query):
    r = subprocess.run(["sf", "data", "query", "-o", org, "--json", "-q", query], capture_output=True, text=True)
    return (json.loads(r.stdout).get("result") or {}).get("records") or [] if r.stdout else []


def outreach_module(block):
    """The reader named by the entry or env, or None."""
    path = os.environ.get("QA_OUTREACH_READER") or block.get("outreach_reader")
    if not path or not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("outreach_reader", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def outreach(o, emails, since):
    tok, hits = o.token(), []
    for e in emails:
        for p in o.get("/api/v2/prospects?filter[emails]=%s" % e, tok)["data"]:
            for s in o.get("/api/v2/sequenceStates?filter[prospect][id]=%s" % p["id"], tok)["data"]:
                if (s["attributes"].get("createdAt") or "") >= since:
                    hits.append("%s prospect %s sequence state %s" % (e, p["id"], s["id"]))
            if (p["attributes"].get("createdAt") or "") >= since:
                hits.append("%s prospect %s made" % (e, p["id"]))
    return hits


def main():
    ids = [a for a in sys.argv[2:] if a.isdigit()]
    if len(sys.argv) < 3 or not ids:
        print(__doc__)
        return 2
    play = sys.argv[1]
    block = tp.play_block(play)
    if len(ids) > 5:
        sys.exit("STOP: the smoke takes up to 5 records")
    org = sf_org(block) if arg("--sf-field") and shutil.which("sf") else None
    if arg("--sf-field") and not org:
        print("skip salesforce readback: needs the `sf` CLI and an org alias (--sf-org, QA_SF_ORG or `sf_org:`)")
    reader = outreach_module(block) if "--outreach" in sys.argv else None
    if "--outreach" in sys.argv and not reader:
        print("skip outreach readback: needs `outreach_reader:` in the targets file entry or env QA_OUTREACH_READER")
    s = tp.load_state(play)
    c = s.get("copy") or {}
    wf = arg("--wf") or c.get("wf") or sys.exit("FAIL: no copy in today's state and no --wf")
    trig = list((c.get("triggers") or {}).values())
    # a manual trigger (a signal play's copy) has no entity: take a segment trigger's, else --entity
    ent = next((t["entity"] for t in trig if t.get("entity")), None) or arg("--entity", "people")
    stand = {v["id"] for v in (c.get("fields") or {}).values()}
    nm = {"companies": names("companies"), "people": names("people")}
    results, fails = [], 0
    for rid in ids:
        rec = records(ent, [rid])[rid]
        pids = [str(x["recordId"]) for x in (rec.get("relatedRecords") or {}).get("items", [])
                if x.get("entityType") == "PEOPLE"] if ent == "companies" else []
        before_p = records("people", pids) if pids else {}
        fields = {nm[ent].get(k, k): v for k, v in rec["fields"].items() if v is not None}
        fields["id"] = int(rid)
        start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        run = tp.clay("workflows", "runs", "test", wf, inp={"fields": fields}, flag="--inputs")
        # an approved run (--approve) answers {"body": {"workflowRun": {"id": ...}}}
        run["runId"] = run.get("runId") or ((run.get("body") or {}).get("workflowRun") or {}).get("id")
        st = tp.wait_run(wf, run["runId"], 600)
        got = steps(wf, run["runId"])
        failed = [(x.get("nodeName"), str(x.get("error") or "")[:160]) for x in got if x.get("status") == "failed"]
        calls = {x.get("nodeName"): x.get("status") for x in got if "(function)" in (x.get("nodeName") or "")}
        time.sleep(5)
        after = records(ent, [rid])[rid]
        after_p = records("people", pids) if pids else {}
        changed = [("record", k, ok) for k, ok in diff(rec["fields"], after["fields"], stand)]
        for p in pids:
            changed += [("person %s" % p, k, ok) for k, ok in
                        diff((before_p.get(p) or {}).get("fields") or {}, (after_p.get(p) or {}).get("fields") or {}, stand)]
        # a field no longer in the field list is a deleted one: Clay drops its old value when the record is
        # written, so it shows as a change but is no live write. Counted apart.
        gone = [("%s %s" % (w, k)) for w, k, ok in changed if not ok and k not in nm[ent if w == "record" else "people"]]
        changed = [c for c in changed if c[2] or c[1] in nm[ent if c[0] == "record" else "people"]]
        live = [("%s %s" % (w, nm[ent if w == "record" else "people"].get(k, k))) for w, k, ok in changed if not ok]
        test = [("%s %s" % (w, nm[ent if w == "record" else "people"].get(k, k))) for w, k, ok in changed if ok]
        written = {}
        for w, k, ok in changed:
            if ok:
                src = after["fields"] if w == "record" else ((after_p.get(w.split()[1]) or {}).get("fields") or {})
                written["%s %s" % (w, nm[ent if w == "record" else "people"].get(k, k))] = src.get(k)
        outputs = {x.get("nodeName"): json.dumps(x.get("stepOutputs"), default=str)[:1500] for x in got
                   if x.get("stepOutputs")}
        r = {"record": rid, "name": fields.get("Company name") or fields.get("Name") or fields.get("name"),
             "run": run["runId"], "status": st.get("status"), "steps": len(got), "failed_steps": failed,
             "calls": calls, "data_credits": st.get("dataCreditsUsed"), "action_credits": st.get("actionCreditsUsed"),
             "live_changed": live, "deleted_cleared": gone, "test_changed": test, "written": written, "outputs": outputs, "start": start}
        sff = arg("--sf-field") if org else None
        if sff:
            acct = fields.get(sff)
            writer = arg("--sf-writer")
            rows = sf(org, "SELECT Id, LastModifiedDate, LastModifiedBy.Name FROM Account WHERE Id = '%s' AND "
                      "LastModifiedDate >= %s" % (acct, start)) if acct else []
            rows += sf(org, "SELECT Id, LastModifiedDate, LastModifiedBy.Name FROM Contact WHERE AccountId = '%s' AND "
                       "LastModifiedDate >= %s" % (acct, start)) if acct else []
            r["salesforce"] = [{"id": x["Id"], "by": (x.get("LastModifiedBy") or {}).get("Name")} for x in rows]
            r["salesforce_fail"] = [x for x in r["salesforce"] if writer and x["by"] == writer]
        if reader:
            emails = [p["fields"].get("email") for p in before_p.values() if p["fields"].get("email")] or \
                     ([fields.get("Email") or fields.get("email")] if ent == "people" else [])
            r["outreach"] = outreach(reader, [e for e in emails if e], start)
        bad = (r["status"] != "completed") + bool(failed) + any(v != "completed" for v in calls.values()) + bool(live) \
            + bool(r.get("salesforce_fail")) + bool(r.get("outreach"))
        fails += bool(bad)
        results.append(r)
        print("%-4s %s %-40s run %s %s, %d steps, %d failed, calls %d/%d, credits %s data %s action, live changed %d, "
              "TEST changed %d%s%s" % (
                  "FAIL" if bad else "PASS", rid, (r["name"] or "")[:40], r["run"], r["status"], r["steps"], len(failed),
                  sum(v == "completed" for v in calls.values()), len(calls), r["data_credits"], r["action_credits"],
                  len(live), len(test), ", salesforce %d changed" % len(r["salesforce"]) if sff else "",
                  ", outreach %d" % len(r["outreach"]) if reader else ""))
        for k, v in sorted(written.items()):
            if k.startswith("record ") and "status" in k:
                print("     did: %s = %s" % (k[7:], str(v)[:120]))
        for line in live:
            print("     live field changed:", line)
        for line in gone:
            print("     deleted field cleared (no live write):", line)
        for n, e in failed:
            print("     failed step:", n, e)
    out = os.path.join(tp.play_dir(play), "tests", "%s-smoke.json" % tp.TODAY)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(results, open(out, "w"), indent=1, default=str)
    data = sum(float(r["data_credits"] or 0) for r in results)
    action = sum(float(r["action_credits"] or 0) for r in results)
    print("smoke %s: %d of %d records pass; credits %.2f data, %.2f action; %s" % (
        "FAIL" if fails else "PASS", len(results) - fails, len(results), data, action, out))
    limit = tp.credit_limit(play)
    if data > limit or action > limit:
        print("STOP: credits are over the limit of %g (data %.2f, action %.2f): the owner's yes comes before any "
              "further run" % (limit, data, action))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
