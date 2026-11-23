"""Shared helpers for the QA scripts: the clay call, the targets file, the run state.

Every script runs from the project root, after the workspace check (`clay whoami`). Targets (the plays or
workflows under test) are listed in a targets file: `--targets <file>`, or env QA_TARGETS, or ./qa/targets.yaml.
Schema: a top key `plays:` (or `targets:`) mapping a target name to its entry:

  doc:             path of the target's doc; its folder holds `tests/` (reports and state)
  name:            display name
  stage:           `test` for a TEST draft that is never live (optional)
  clay_ids:        {workflows: {wf_id: name}, segments: {seg_id: name}, fields: {field_id: name}}
  repo_checks:     shell commands that must pass, `{target}` is replaced by the name (optional)
  convention:      `ior_t` turns on the (i)/(r)/(o)/(t) segment and status column checks (optional)
  credit_limit:    credits above which a run needs the owner's yes (optional, default 20; env QA_CREDIT_LIMIT)
  sf_org:          Salesforce CLI org alias for the smoke readback (optional; env QA_SF_ORG)
  outreach_reader: path of a python file with token() and get(path, token) for the Outreach readback (optional;
                   env QA_OUTREACH_READER)

The state file of one test run lives in the target's folder (`<doc folder>/tests/<date>-state.json`) and holds
only ids of the TEST parts it made, so the cleanup step can find them in a later session.
"""
import datetime
import json
import os
import subprocess
import sys
import time

import yaml

ROOT = os.getcwd()


def _take_targets():
    """Pull `--targets <file>` out of argv, so the scripts' positional parsing never sees it."""
    if "--targets" in sys.argv:
        i = sys.argv.index("--targets")
        path = sys.argv[i + 1] if i + 1 < len(sys.argv) else sys.exit("FAIL: --targets needs a file")
        del sys.argv[i:i + 2]
        return path
    return os.environ.get("QA_TARGETS") or os.path.join(ROOT, "qa", "targets.yaml")


REGISTRY = _take_targets()
AUD = "b1ab3d5d-b0db-4b30-9251-3f32d8b103c1"   # the Audiences action package (Clay's, the same in every workspace)
WRITE_ACTIONS = ("update-audiences-record", "upsert-audiences-record")
TODAY = datetime.date.today().isoformat()


def clay(*args, inp=None, flag="--input", ok_fail=False):
    """One clay CLI call, JSON in by stdin, JSON out. A failure stops the script unless ok_fail."""
    cmd = ["clay", *args] + ([flag, "-"] if inp is not None else [])
    r = subprocess.run(cmd, capture_output=True, text=True, input=json.dumps(inp) if inp is not None else None)
    if r.returncode and "approval_required" in (r.stdout or r.stderr) and "--approve" in sys.argv:
        # Clay asks a human to approve some CLI actions (test runs, field deletes; seen 2026-11-19). --approve says
        # the operator gave the yes for this step by name (SKILL.md, "What needs a yes"): approve and go on.
        aid = json.loads(r.stdout or r.stderr)["error"]["details"]["actionApprovalRequestId"]
        a = subprocess.run(["clay", "approvals", "approve", aid], capture_output=True, text=True)
        if a.returncode:
            sys.exit("FAIL approve %s\n%s" % (aid, (a.stdout or a.stderr)[-800:]))
        res = json.loads(a.stdout).get("result")
        print("approved %s (%s)" % (aid, " ".join(args[:3])), file=sys.stderr)
        return res if isinstance(res, dict) else {"result": res}
    if r.returncode:
        if ok_fail:
            return {"_error": (r.stdout or r.stderr)[-800:]}
        sys.exit("FAIL clay %s\n%s\n%s" % (" ".join(args[:6]), r.stdout[-1500:], r.stderr[-600:]))
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return out


def unwrap(d):
    return d.get("data", d) if isinstance(d, dict) and isinstance(d.get("data"), dict) else d


def registry():
    if not os.path.exists(REGISTRY):
        sys.exit("FAIL: no targets file at %s (--targets <file>, or env QA_TARGETS)" % REGISTRY)
    data = yaml.safe_load(open(REGISTRY)) or {}
    return data.get("plays") or data.get("targets") or sys.exit("FAIL: %s has no `plays:` or `targets:` key" % REGISTRY)


def play_block(play):
    plays = registry()
    if play not in plays:
        sys.exit("FAIL: no target %r in %s. Targets: %s" % (play, REGISTRY, ", ".join(plays)))
    return plays[play]


def credit_limit(play):
    """Credits above which a run needs the owner's yes: env QA_CREDIT_LIMIT, else the entry's, else 20."""
    return float(os.environ.get("QA_CREDIT_LIMIT") or play_block(play).get("credit_limit") or 20)


def play_dir(play):
    return os.path.dirname(os.path.join(ROOT, play_block(play)["doc"]))


def state_path(play, day=TODAY):
    return os.path.join(play_dir(play), "tests", "%s-state.json" % day)


def load_state(play, day=TODAY):
    p = state_path(play, day)
    return json.load(open(p)) if os.path.exists(p) else {}


def save_state(play, s, day=TODAY):
    p = state_path(play, day)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(s, open(p, "w"), indent=1, sort_keys=True)


def retired(name):
    return name.startswith(("SUNSET:", "ZZ DELETE:", "ZZ "))


def wait_run(wf, run_id, seconds=180):
    """Wait for one run to end. Returns the run."""
    end = time.time() + seconds
    while True:
        st = clay("workflows", "runs", "get", run_id)
        if st.get("status") in ("completed", "failed", "terminated", "cancelled") or time.time() > end:
            return st
        time.sleep(4)


def node_test(wf, nid, inputs, seconds=180):
    """Test one step with typed inputs. Returns (outputs, run id, status). A write step still writes."""
    run = clay("workflows", "nodes", "test", wf, nid, inp=inputs, flag="--inputs")
    st = wait_run(wf, run["runId"], seconds)
    steps = clay("workflows", "runs", "steps", wf, run["runId"], "--node-id", nid).get("data") or []
    out = (steps[0].get("stepOutputs") or {}) if steps else {}
    return out, run["runId"], st.get("status")
