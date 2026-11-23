"""Render one results file into one self contained HTML page.

    python3 skills/clay-workflow-qa/scripts/render_page.py <target folder>/tests/<date>-qa.json
        [--fragment <path>]   also write the page body for an Artifact publish (no doctype or head)

The results file follows the results-page reference. The page is written next to it with the same stem (`.html`): no
outside calls, light and dark, phone width, one small inline script for the fix list. The page answers one question, "did it work?", for
someone who does not build workflows (the client team or the owner).
Above the fold: the verdict, a checklist, one line a test account, what needs fixing and who decides, what
was not tested. Everything else sits in one closed "Details for builders" section.

The script checks the results file first and stops with every gap listed, so a run with a gap has no page.
That check includes plain words: a builder word in a text shown above the fold is a gap. The verdict and the
confidence level are computed here; the results file gives only the sentence why.

The fix list: each open alert and finding has an "Add to fix list"
toggle. The chosen items fill a box at the bottom with a ready Claude Code prompt, built here by `fix_prompt()`:
the play, the date, the report path, each chosen item with its builder detail, and a rerun of the test. Builder
words are fine inside the prompt; the gate reads only the page.
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "inter.css")

# The ladder, in order: (id, the builder's name, the plain name on the checklist).
STEPS = [
    ("0", "Spec", "Listed every rule in the play doc"),
    ("a", "Static check", "Checked the setup matches the doc"),
    ("b", "Step tests", "Tested each decision the play makes"),
    ("c", "Dry run smoke", "Tried it on real accounts without sending"),
    ("d", "Trigger test", "Let it start by itself on a test account"),
    ("e", "Canary", "Sent for real on one account"),
    ("f", "Review", "Looked for problems and improvements"),
]
STEP_IDS = [s[0] for s in STEPS]
STEP_RESULTS = ("PASS", "FAIL", "SKIPPED", "NOT RUN")
RULE_RESULTS = ("PASS", "FAIL", "NO TEST", "MODULE")
SEVERITIES = ("high", "medium", "low")
ALERT_STATUS = ("open", "ruled", "fixed")
ALERT_KINDS = ("alert", "finding")
VERDICT_WORDS = {"ready": "Ready to go live", "fix": "Fix first", "blocked": "Blocked"}
CONF_WORDS = {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"}
CONF_WHY = {"high": "Every check ran in this test.",
            "medium": "Some checks were done in an earlier test and not repeated, or did not run.",
            "low": "Something failed, has no test, or the test stopped early."}
STEP_WORDS = {"PASS": "Passed", "FAIL": "Failed", "SKIPPED": "Skipped", "NOT RUN": "Not run"}
RULE_WORDS = {"PASS": "Proven", "FAIL": "Failed", "NO TEST": "No test", "MODULE": "Shared part only"}
STATE = {"PASS": "pass", "FAIL": "fail", "SKIPPED": "idle", "NOT RUN": "idle", "NO TEST": "warn", "MODULE": "warn"}

# Builder words kept off the top of the page. Say what it means instead ("the list that starts the play",
# "a test run that sends nothing"). Ids, reason codes and costs go in `ids` or the details.
JARGON = [
    (r"\bsegments?\b", "segment"), (r"\btriggers?\b", "trigger"), (r"\bnodes?\b", "node"),
    (r"\bstatus columns?\b", "status column"), (r"\bdry run\b", "dry run"), (r"\bworkflows?\b", "workflow"),
    (r"\bsnapshots?\b", "snapshot"), (r"\bwebhooks?\b", "webhook"), (r"\bcredits?\b", "credit"),
    (r"\bClay\b", "Clay"), (r"\b(wfr|wfs|wf|wfn|audseg|audf)_\w+", "a Clay id"),
    (r"\b[A-Z]{2,}_[A-Z_]{2,}\b", "a reason code"), (r"`", "a backtick"), (r"\((i|t|r|o)\)", "a segment code"),
    (r"\b[SW]:\d+", "a doc line"),
]


def jargon(text):
    """The builder words in one text, as names."""
    return [name for pat, name in JARGON if re.search(pat, text or "", flags=re.I if name != "a reason code" else 0)]


# ---------- checks ----------

def check(d):
    """Every gap in the results file, as plain lines. An empty list means the page can be drawn."""
    gaps = []

    def need(obj, key, where):
        if not isinstance(obj, dict) or obj.get(key) in (None, "", []):
            gaps.append("%s: `%s` is missing" % (where, key))
            return False
        return True

    def plain(text, where):
        hits = jargon(text)
        if hits:
            gaps.append("%s: plain words only above the fold, found %s" % (where, ", ".join(sorted(set(hits)))))

    for key in ("play", "date", "run_label", "ran_by", "target"):
        need(d, key, "top")
    if need(d, "verdict", "top") and need(d["verdict"], "why", "verdict"):
        plain(d["verdict"]["why"], "verdict.why")
    if not isinstance(d.get("credits"), dict) or not isinstance(d["credits"].get("limit"), (int, float)):
        gaps.append("credits: `limit` is missing (a number)")

    steps = d.get("steps") or []
    ids = [s.get("id") for s in steps]
    if ids != STEP_IDS:
        gaps.append("steps: need one row for each of %s, in that order (got %s)" % (", ".join(STEP_IDS), ids))
    for s in steps:
        where = "step %s" % s.get("id")
        if s.get("result") not in STEP_RESULTS:
            gaps.append("%s: `result` must be one of %s" % (where, ", ".join(STEP_RESULTS)))
            continue
        if s["result"] in ("PASS", "FAIL"):
            need(s, "bar", where)
            need(s, "proof", where)
            if need(s, "plain", where):
                plain(s["plain"], where + " plain")
        elif need(s, "why", where):
            plain(s["why"], where + " why")
        cr = s.get("credits")
        if not isinstance(cr, dict) or not all(isinstance(cr.get(k), (int, float)) for k in ("data", "action")):
            gaps.append("%s: `credits` needs `data` and `action` numbers (0 when free)" % where)

    by_id = {s.get("id"): s for s in steps}
    spec_ran = by_id.get("0", {}).get("result") in ("PASS", "FAIL")
    rules = d.get("rules") or []
    if spec_ran and not rules:
        gaps.append("rules: step 0 ran, so every rule of the doc needs a row")
    for r in rules:
        where = "rule %s" % r.get("n")
        for key in ("n", "rule", "expected"):
            need(r, key, where)
        if r.get("result") not in RULE_RESULTS:
            gaps.append("%s: `result` must be one of %s" % (where, ", ".join(RULE_RESULTS)))
        elif r["result"] != "NO TEST":
            need(r, "test", where)
            need(r, "actual", where)

    ran = lambda i: by_id.get(i, {}).get("result") in ("PASS", "FAIL") or by_id.get(i, {}).get("from")
    records = d.get("records") or []
    if ran("c") and not records:
        gaps.append("records: step c ran, so each smoke record needs a row")
    for r in records:
        where = "record %s" % r.get("name")
        for key in ("name", "why", "expected", "actual"):
            need(r, key, where)
        if need(r, "line", where):
            plain(r["line"], where + " line")
        if r.get("equal") not in (True, False, None):
            gaps.append("%s: `equal` must be true, false or null" % where)

    trig = d.get("trigger")
    if ran("d") and not trig:
        gaps.append("trigger: step d ran, so the timeline is needed")
    if trig:
        events = trig.get("events") or []
        if not events:
            gaps.append("trigger: `events` is missing")
        for ev in events:
            need(ev, "label", "trigger event")
            if ev.get("at"):
                try:
                    _ts(ev["at"])
                except ValueError:
                    gaps.append("trigger event %r: `at` is not an ISO time" % ev.get("label"))

    for a in d.get("alerts") or []:
        where = "alert %r" % a.get("title")
        for key in ("key", "title", "why", "fix", "decides"):
            need(a, key, where)
        if a.get("status") == "open":
            for key in ("title", "fix", "decides"):
                plain(a.get(key), "%s %s" % (where, key))
        if a.get("severity") not in SEVERITIES:
            gaps.append("%s: `severity` must be one of %s" % (where, ", ".join(SEVERITIES)))
        if a.get("status") not in ALERT_STATUS:
            gaps.append("%s: `status` must be one of %s" % (where, ", ".join(ALERT_STATUS)))
        known = {str(r.get("n")) for r in d.get("rules") or []}
        for n in a.get("rules") or []:
            if str(n) not in known:
                gaps.append("%s: `rules` names rule %s, which is not in `rules`" % (where, n))
        if a.get("kind") not in ALERT_KINDS:
            gaps.append("%s: `kind` must be alert or finding" % where)

    if not d.get("cleanup") and not d.get("cleanup_none"):
        gaps.append("cleanup: list each part the test made with its read back, or give `cleanup_none` (why nothing was made)")
    for c in d.get("cleanup") or []:
        for key in ("part", "proof"):
            need(c, key, "cleanup %r" % c.get("part"))
        if c.get("gone") not in (True, False):
            gaps.append("cleanup %r: `gone` must be true or false" % c.get("part"))
    return gaps


# ---------- the computed reads ----------

def verdict(d):
    """ready, fix or blocked. Ready: every step passed or has a reason it did not run, every rule proven,
    no open alert, every record equal. Blocked: the results file says what stopped the run."""
    if d.get("blocked"):
        return "blocked"
    if any(s["result"] == "FAIL" for s in d["steps"]):
        return "fix"
    if any(r["result"] != "PASS" for r in d.get("rules") or []):
        return "fix"
    if any(a["status"] == "open" and a["kind"] == "alert" for a in d.get("alerts") or []):
        return "fix"
    if any(r.get("equal") is False for r in d.get("records") or []):
        return "fix"
    return "ready"


def confidence(d):
    """high: steps 0 to d all passed in this run. medium: nothing failed, but a step was carried from an
    earlier run or did not run. low: a step or a rule failed, a rule has no test, or the run was blocked."""
    steps = {s["id"]: s for s in d["steps"]}
    if d.get("blocked") or any(s["result"] == "FAIL" for s in d["steps"]):
        return "low"
    if any(r["result"] in ("FAIL", "NO TEST") for r in d.get("rules") or []):
        return "low"
    if all(steps[i]["result"] == "PASS" and not steps[i].get("from") for i in ("0", "a", "b", "c", "d")):
        return "high"
    return "medium"


def proven(d):
    rules = d.get("rules") or []
    return sum(1 for r in rules if r["result"] == "PASS"), len(rules)


def compare(d, prev):
    """What changed against the previous results file: lists of (kind, text). kind is new, fixed or changed."""
    out = []
    v0, v1 = verdict(prev), verdict(d)
    if v0 != v1:
        out.append(("fixed" if v1 == "ready" else "changed",
                    "Verdict was %s, now %s." % (VERDICT_WORDS[v0], VERDICT_WORDS[v1])))
    p0, p1 = proven(prev), proven(d)
    if p0 != p1:
        out.append(("fixed" if p1[0] - p1[1] >= p0[0] - p0[1] else "new",
                    "Rules proven: was %d of %d, now %d of %d." % (p0 + p1)))
    names = {i: n for i, n, _ in STEPS}
    ps = {s["id"]: s for s in prev.get("steps") or []}
    for s in d["steps"]:
        old = ps.get(s["id"])
        if old and old["result"] != s["result"]:
            kind = "new" if s["result"] == "FAIL" else ("fixed" if old["result"] == "FAIL" else "changed")
            out.append((kind, "%s: was %s, now %s." % (names[s["id"]], STEP_WORDS[old["result"]].lower(),
                                                       STEP_WORDS[s["result"]].lower())))
    pr = {str(r["n"]): r for r in prev.get("rules") or []}
    for r in d.get("rules") or []:
        old = pr.get(str(r["n"]))
        if old is None:
            out.append(("new" if r["result"] != "PASS" else "changed",
                        "New rule %s: %s (%s)." % (r["n"], r["rule"], RULE_WORDS[r["result"]].lower())))
        elif old["result"] != r["result"]:
            kind = "fixed" if r["result"] == "PASS" else "new"
            out.append((kind, "Rule %s, %s: was %s, now %s." % (r["n"], r["rule"], RULE_WORDS[old["result"]].lower(),
                                                                 RULE_WORDS[r["result"]].lower())))
        elif old.get("expected") != r.get("expected"):
            out.append(("changed", "Rule %s now expects: %s" % (r["n"], r["expected"])))
    pa = {a["key"]: a for a in prev.get("alerts") or []}
    ca = {a["key"]: a for a in d.get("alerts") or []}
    for k, a in ca.items():
        old = pa.get(k)
        if a["status"] == "open" and (old is None or old["status"] != "open"):
            out.append(("new", "New %s: %s" % (a["kind"], a["title"])))
        elif old and old["status"] == "open" and a["status"] != "open":
            out.append(("fixed", "Closed (%s): %s" % (a["status"], a["title"])))
    for k, a in pa.items():
        if k not in ca and a["status"] == "open":
            out.append(("fixed", "Closed: %s" % a["title"]))
    return out


def cleanup_state(d):
    """(result, plain line) for the checklist's last row."""
    cl = d.get("cleanup") or []
    if not cl:
        return "SKIPPED", d["cleanup_none"]
    left = sum(1 for c in cl if not c["gone"])
    if left:
        return "FAIL", "%d of %d things the test made are still there." % (left, len(cl))
    return "PASS", "Everything the test made is gone, checked one by one (%d of %d)." % (len(cl), len(cl))


# ---------- drawing ----------

def e(x):
    return html.escape("" if x is None else str(x), quote=True)


def _ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def chip(state, text):
    return '<span class="chip chip--%s">%s</span>' % (state, e(text))


def fmt_num(x):
    return ("%g" % round(x, 2)) if isinstance(x, (int, float)) else e(x)


def human_date(s):
    try:
        return datetime.date.fromisoformat(s).strftime("%-d %B %Y")
    except ValueError:
        return s


def mark(state):
    return '<span class="mark mark--%s" aria-hidden="true"></span>' % state


def section(sid, title, body):
    return '<section class="sec" id="%s" aria-labelledby="%s-h"><h2 id="%s-h">%s</h2>%s</section>' % (sid, sid, sid, e(title), body)


def draw_verdict(d):
    v, c = verdict(d), confidence(d)
    state = {"ready": "pass", "fix": "warn", "blocked": "fail"}[v]
    blocked = ""
    if d.get("blocked"):
        b = d["blocked"]
        blocked = '<p class="verdict-block">Stopped by: %s. Who decides: %s.</p>' % (e(b.get("reason")), e(b.get("decides")))
    return ('<section class="verdict verdict--%s" aria-label="Verdict"><p class="verdict-word">%s%s</p>'
            '<p class="verdict-why">%s</p>%s<p class="verdict-conf">%s. %s</p></section>'
            % (state, mark(state), e(VERDICT_WORDS[v]), e(d["verdict"]["why"]), blocked, e(CONF_WORDS[c]), e(CONF_WHY[c])))


def draw_checklist(d):
    rows = []
    for (sid, _, name), s in zip(STEPS, d["steps"]):
        if s["result"] in ("PASS", "FAIL"):
            st, word, line = STATE[s["result"]], STEP_WORDS[s["result"]], s["plain"]
            if s.get("from"):
                word = "Passed earlier" if s["result"] == "PASS" else "Failed earlier"
        else:
            st, word, line = "idle", STEP_WORDS[s["result"]], s["why"]
        rows.append((st, name, line, word))
    res, line = cleanup_state(d)
    rows.append((STATE[res], "Cleaned up", line, {"PASS": "Done", "FAIL": "Not done", "SKIPPED": "Nothing to clean"}[res]))
    body = "".join('<li>%s<span class="ck-text"><b>%s</b><span>%s</span></span><span class="ck-word ck-word--%s">%s</span></li>'
                   % (mark(st), e(name), e(line), st, e(word)) for st, name, line, word in rows)
    return section("checked", "What we checked", '<ol class="checklist">%s</ol>' % body)


def draw_accounts(d):
    recs = d.get("records") or []
    if not recs:
        return ""
    body = "".join('<li>%s<span>%s</span></li>' % (mark({True: "pass", False: "fail", None: "idle"}[r.get("equal")]), e(r["line"]))
                   for r in recs)
    note = '<p class="note">From the test earlier today.</p>' if d.get("records_from") else ""
    return section("accounts", "What the test accounts did", '<ul class="lines">%s</ul>%s' % (body, note))


def draw_fixes(d):
    opened = [a for a in d.get("alerts") or [] if a["status"] == "open"]
    sev = {"high": 0, "medium": 1, "low": 2}
    if not opened:
        return section("fix", "What needs fixing", '<p class="ok">Nothing.</p>')
    groups = []
    for kind, title in (("alert", "Before it goes live"), ("finding", "Can wait")):
        items = sorted([a for a in opened if a["kind"] == kind], key=lambda a: sev[a["severity"]])
        if not items:
            continue
        st = "warn" if kind == "alert" else "idle"
        lis = "".join('<li>%s<span class="fx-text"><b>%s</b><span><span class="lbl">What to do:</span> %s</span>'
                      '<span><span class="lbl">Who decides:</span> %s</span>%s</span></li>'
                      % (mark(st), e(a["title"]), e(a["fix"]), e(a["decides"]), add_button(a)) for a in items)
        groups.append('<div class="fx-group"><h3>%s</h3><ul class="fixes">%s</ul></div>' % (e(title), lis))
    return section("fix", "What needs fixing", "".join(groups))


def add_button(a):
    return ('<button type="button" class="add" data-key="%s" aria-pressed="false" hidden>'
            '<span class="add-plus" aria-hidden="true"></span><span class="add-word">Add to fix list</span></button>' % e(a["key"]))


# ----- the fix list -----

def fix_prompt(d):
    """The prompt pieces the fix list joins: {header, items: {key: text}, footer}. Builder detail is welcome here."""
    folder = os.path.dirname(d.get("_file", ""))
    report = os.path.join(folder, d["report"]) if d.get("report") else "(no report file)"
    header = ("Fix list from the %s test of %s (%s).\n"
              "Report: %s. Results file: %s.\n\n"
              "Read the report first. Then work through the items below, one at a time. Where an item names who "
              "decides and that is not you, ask them before you change anything live or paid. When the fixes are in, "
              "run Skill(clay-workflow-qa) on %s again and draw a new page, with `previous` set to %s.\n\n"
              "Items:\n" % (d["play"], d["date"], d["run_label"], report, d.get("_file", ""), d["play"],
                              os.path.basename(d.get("_file", "")) or "this results file"))
    rules = {str(r["n"]): r for r in d.get("rules") or []}
    items = {}
    for a in d.get("alerts") or []:
        if a["status"] != "open":
            continue
        lines = ["\n- %s" % a["title"],
                 "  Kind: %s, %s severity%s. Key: %s." % (a["kind"], a["severity"],
                                                         ", stops go live" if a["kind"] == "alert" else "", a["key"]),
                 "  What to do: %s" % a["fix"],
                 "  Who decides: %s" % a["decides"],
                 "  Why: %s" % a["why"]]
        if a.get("record"):
            lines.append("  Record: %s" % a["record"])
        for n in a.get("rules") or []:
            r = rules.get(str(n))
            if r:
                lines.append("  Rule %s: %s (doc %s). Expected: %s. Test: %s." % (
                    r["n"], r["rule"], r.get("doc_line", "no line"), r["expected"], r.get("test", "none")))
        items[a["key"]] = "\n".join(lines) + "\n"
    ids = d.get("ids") or []
    footer = ("\nIds from this run:\n" + "".join("- %s: %s\n" % (i["label"], i["value"]) for i in ids)) if ids else ""
    return {"header": header, "items": items, "footer": footer,
            "store": "qa-fixlist:%s:%s:%s" % (d["play"], d["date"], d["run_label"])}


def draw_fixbar(d):
    fp = fix_prompt(d)
    if not fp["items"]:
        return ""
    data = json.dumps(fp, ensure_ascii=False).replace("</", "<\\/")
    return ('<script type="application/json" id="fix-data">%s</script>'
            '<aside class="fixbar" id="fixbar" aria-label="Fix list" hidden>'
            '<div class="fb-in"><div class="fb-head">'
            '<button type="button" class="fb-toggle" id="fb-toggle" aria-expanded="false" aria-controls="fb-body">'
            '<b>Fix list</b> <span id="fb-count"></span><span class="fb-chev" aria-hidden="true"></span></button>'
            '<button type="button" class="fb-copy" id="fb-copy">Copy prompt</button></div>'
            '<div class="fb-body" id="fb-body" hidden>'
            '<label class="fb-label" for="fb-text">A prompt for Claude Code. Edit it if you like, then copy it.</label>'
            '<textarea id="fb-text" rows="12" spellcheck="false"></textarea>'
            '<div class="fb-foot"><span class="fb-status" id="fb-status" role="status" aria-live="polite"></span>'
            '<button type="button" class="fb-clear" id="fb-clear">Clear the list</button></div>'
            '</div></div></aside><script>%s</script>' % (data, JS))


def draw_not_tested(d):
    items = []
    for (sid, _, name), s in zip(STEPS, d["steps"]):
        if s["result"] in ("SKIPPED", "NOT RUN"):
            items.append((name, s["why"]))
        elif s.get("from"):
            items.append((name, "Done in an earlier test today, not repeated."))
    gaps = [r for r in d.get("rules") or [] if r["result"] in ("NO TEST", "MODULE")]
    if gaps:
        items.append(("%d %s of the play doc" % (len(gaps), "rule" if len(gaps) == 1 else "rules"),
                      "Has no test of its own yet. The list is in the details below."))
    if not items:
        return section("not-tested", "Not tested", '<p class="ok">Everything was tested in this run.</p>')
    body = "".join('<li>%s<span><b>%s.</b> %s</span></li>' % (mark("idle"), e(n), e(w)) for n, w in items)
    return section("not-tested", "Not tested", '<ul class="lines">%s</ul>' % body)


# ----- details for builders -----

def sub(title, body):
    return '<div class="dt-block"><h3>%s</h3>%s</div>' % (e(title), body)


def d_run(d):
    rows = [("Ran by", d["ran_by"]), ("Target", d["target"]), ("Run", d["run_label"]), ("Report", d.get("report", ""))]
    return sub("This run", '<dl class="kv">%s</dl>' % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (e(k), e(v)) for k, v in rows if v))


def d_steps(d):
    rows = []
    for (sid, bname, _), s in zip(STEPS, d["steps"]):
        cr = s["credits"]
        rows.append('<tr><td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="num">%s, %s</td></tr>'
                    % (e(sid), e(bname), chip(STATE[s["result"]], STEP_WORDS[s["result"]]), e(s.get("bar", "")),
                       e(s.get("proof") or s.get("why", "")) + ((' <span class="muted">From %s.</span>' % e(s["from"])) if s.get("from") else ""),
                       fmt_num(cr["data"]), fmt_num(cr["action"])))
    return sub("Steps: pass bar and proof", '<div class="scroll"><table><thead><tr><th>#</th><th>Step</th><th>Result</th>'
               '<th>Pass bar, set before the run</th><th>Proof</th><th>Credits (data, action)</th></tr></thead><tbody>%s</tbody>'
               '</table></div>' % "".join(rows))


def d_rules(d):
    rules = d.get("rules") or []
    if not rules:
        return ""
    p, n = proven(d)
    rows = "".join('<tr><td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                   % (e(r["n"]), e(r["rule"]), e(r.get("doc_line", "")), e(r["expected"]), e(r.get("actual", "")),
                      e(r.get("test", "")), chip(STATE[r["result"]], RULE_WORDS[r["result"]])) for r in rules)
    return sub("Rules of the play doc: %d of %d proven" % (p, n),
               '<div class="scroll"><table><thead><tr><th>#</th><th>Rule</th><th>Doc line</th><th>Expected</th><th>Actual</th>'
               '<th>Test</th><th></th></tr></thead><tbody>%s</tbody></table></div>' % rows)


def d_records(d):
    recs = d.get("records") or []
    if not recs:
        return ""
    rows = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                   % (e(r["name"]), e(r["why"]), e(r["expected"]), e(r["actual"]) + ((' <span class="muted">%s</span>' % e(r["note"])) if r.get("note") else ""),
                      chip({True: "pass", False: "fail", None: "idle"}[r.get("equal")], {True: "Equal", False: "Not equal", None: "Not compared"}[r.get("equal")]))
                   for r in recs)
    note = ('<p class="muted">From %s.</p>' % e(d["records_from"])) if d.get("records_from") else ""
    return sub("Records", '<div class="scroll"><table><thead><tr><th>Record</th><th>Why picked</th><th>The doc predicts</th>'
               '<th>The run wrote</th><th></th></tr></thead><tbody>%s</tbody></table></div>%s' % (rows, note))


def d_trigger(d):
    t = d.get("trigger")
    if not t:
        return ""
    ev = t["events"]
    timed = [x for x in ev if x.get("at")]
    t0 = _ts(timed[0]["at"]) if timed else None
    limit = t.get("limit_minutes") or 90
    span = max([limit] + [(_ts(x["at"]) - t0).total_seconds() / 60 for x in timed]) if t0 else limit
    marks, items = [], []
    for x in ev:
        mins = round((_ts(x["at"]) - t0).total_seconds() / 60) if x.get("at") else None
        when = ("%s UTC" % _ts(x["at"]).strftime("%H:%M")) if x.get("at") else "Time not recorded"
        after = ("minute %d" % mins) if mins is not None else ""
        st = x.get("state", "pass")
        if mins is not None:
            marks.append('<span class="tick tick--%s" style="left:%.2f%%" title="%s"></span>'
                         % (st, 100.0 * mins / span, e("%s, %s" % (x["label"], after))))
        items.append('<li>%s<span class="tl-label">%s<small>%s</small></span><span class="tl-when">%s<small>%s</small></span></li>'
                     % (mark(st), e(x["label"]), e(x.get("note", "")), e(when), e(after)))
    lim = '<span class="limit" style="left:%.2f%%"><span>%d minute limit</span></span>' % (100.0 * limit / span, limit)
    track = '<div class="track" aria-hidden="true"><span class="rail"></span>%s%s</div>' % (lim, "".join(marks))
    note = ('<p class="muted">From %s.</p>' % e(t["from"])) if t.get("from") else ""
    lead = ('<p>%s</p>' % e(t["summary"])) if t.get("summary") else ""
    return sub("Trigger test timeline", '%s%s<ol class="tl">%s</ol>%s' % (lead, track, "".join(items), note))


def d_alerts(d):
    al = d.get("alerts") or []
    if not al:
        return ""
    order = {"open": 0, "ruled": 1, "fixed": 1}
    sev = {"high": 0, "medium": 1, "low": 2}
    al = sorted(al, key=lambda a: (order[a["status"]], a["kind"] != "alert", sev[a["severity"]]))
    rows = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                   % (chip("idle", "%s, %s" % (a["kind"].capitalize(), a["status"] if a["status"] != "open" else a["severity"])),
                      e(a["title"]), e(a["why"]), e(a.get("record", "")), e(a["fix"])) for a in al)
    return sub("Alerts and findings, with why and the record", '<div class="scroll"><table><thead><tr><th></th><th>What</th>'
               '<th>Why it matters</th><th>Record</th><th>What to do</th></tr></thead><tbody>%s</tbody></table></div>' % rows)


def d_credits(d):
    lim = d["credits"]["limit"]
    total = sum(s["credits"]["data"] + s["credits"]["action"] for s in d["steps"] if not s.get("from"))
    carried = sum(s["credits"]["data"] + s["credits"]["action"] for s in d["steps"] if s.get("from"))
    line = "%s of the %s credit limit spent in this run." % (fmt_num(total), fmt_num(lim))
    if carried:
        line += " Steps shown from an earlier run spent %s then." % fmt_num(carried)
    return sub("Credits", "<p>%s The steps table has the split by step.</p>" % e(line))


def d_cleanup(d):
    cl = d.get("cleanup") or []
    if not cl:
        return sub("Cleanup", "<p>%s</p>" % e(d["cleanup_none"]))
    rows = "".join('<li>%s<span><b>%s</b><small>%s</small></span></li>' % (mark("pass" if c["gone"] else "fail"), e(c["part"]), e(c["proof"]))
                   for c in cl)
    note = ('<p class="muted">From %s.</p>' % e(d["cleanup_from"])) if d.get("cleanup_from") else ""
    return sub("Cleanup, read back", '<ul class="lines">%s</ul>%s' % (rows, note))


def d_compare(d, prev, prev_name):
    if prev is None:
        return sub("Compared to the last run", "<p>No earlier results file: this is the first run on file.</p>")
    ch = compare(d, prev)
    label = "%s, %s" % (prev.get("run_label", prev_name), human_date(prev.get("date", "")))
    if not ch:
        return sub("Compared to the last run (%s)" % label, "<p>Nothing changed.</p>")
    lis = "".join("<li>%s<span>%s</span></li>" % (chip({"new": "fail", "fixed": "pass", "changed": "idle"}[k],
                                                        {"new": "New", "fixed": "Fixed", "changed": "Changed"}[k]), e(t)) for k, t in ch)
    return sub("Compared to the last run (%s)" % label, '<ul class="lines">%s</ul>' % lis)


def d_ids(d):
    ids = d.get("ids") or []
    rows = "".join("<div><dt>%s</dt><dd><code>%s</code></dd></div>" % (e(i["label"]), e(i["value"])) for i in ids)
    rows += "<div><dt>Results file</dt><dd><code>%s</code></dd></div>" % e(d.get("_file", ""))
    return sub("Ids", '<dl class="kv">%s</dl>' % rows)


def draw_details(d, prev, prev_name):
    parts = [d_run(d), d_steps(d), d_rules(d), d_records(d), d_trigger(d), d_alerts(d), d_credits(d), d_cleanup(d),
             d_compare(d, prev, prev_name), d_ids(d)]
    return ('<details class="details" id="details"><summary>Details for builders</summary><div class="dt-body">%s</div></details>'
            % "".join(parts))


def page_parts(d, prev=None, prev_name=""):
    title = "%s test, %s" % (d["play"], d["date"])
    head = '<header class="top"><h1>%s</h1><p class="sub">Test of %s.</p></header>' % (e(d["play"]), e(human_date(d["date"])))
    body = "".join([head, draw_verdict(d), draw_checklist(d), draw_accounts(d), draw_fixes(d), draw_not_tested(d),
                    draw_details(d, prev, prev_name), draw_fixbar(d)])
    return title, '<main class="page">%s</main>' % body


def fonts():
    try:
        with open(FONTS) as f:
            return f.read()
    except OSError:
        return ""


def render(d, prev=None, prev_name="", fragment=False):
    title, body = page_parts(d, prev, prev_name)
    style = "<style>%s\n%s</style>" % (fonts(), CSS)
    top = '<title>%s</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n%s\n' % (e(title), style)
    if fragment:
        return top + body + "\n"
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n%s</head>\n'
            '<body>\n%s\n</body>\n</html>\n' % (top, body))


def load(path):
    with open(path) as f:
        d = json.load(f)
    d["_file"] = os.path.relpath(path)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("results")
    ap.add_argument("--fragment", help="also write the page body for an Artifact publish to this path")
    a = ap.parse_args(argv)
    d = load(a.results)
    gaps = check(d)
    if gaps:
        sys.exit("FAIL: the results file has %d gaps, so no page was drawn:\n- %s" % (len(gaps), "\n- ".join(gaps)))
    prev, prev_name = None, ""
    if d.get("previous"):
        pp = os.path.join(os.path.dirname(a.results), d["previous"])
        if not os.path.exists(pp):
            sys.exit("FAIL: `previous` names %s, which does not exist" % pp)
        prev, prev_name = load(pp), d["previous"]
        pg = check(prev)
        if pg:
            sys.exit("FAIL: the previous results file %s has gaps:\n- %s" % (pp, "\n- ".join(pg)))
    out = os.path.splitext(a.results)[0] + ".html"
    with open(out, "w") as f:
        f.write(render(d, prev, prev_name))
    if a.fragment:
        with open(a.fragment, "w") as f:
            f.write(render(d, prev, prev_name, fragment=True))
    v, c = verdict(d), confidence(d)
    p, n = proven(d)
    print("OK page: %s\n   verdict: %s, %s; %d of %d rules proven" % (out, VERDICT_WORDS[v], CONF_WORDS[c].lower(), p, n))
    if a.fragment:
        print("   artifact body: %s" % a.fragment)


JS = r"""
(function(){
  var el=function(id){return document.getElementById(id)};
  var src=el('fix-data'); if(!src) return;
  var data=JSON.parse(src.textContent);
  var bar=el('fixbar'), ta=el('fb-text'), body=el('fb-body'), tog=el('fb-toggle'), count=el('fb-count'),
      copy=el('fb-copy'), status=el('fb-status'), page=document.querySelector('.page');
  var buttons=[].slice.call(document.querySelectorAll('button.add'));
  var chosen=[], edited=false, opened=false, timer=null;
  try { chosen=JSON.parse(localStorage.getItem(data.store)||'[]').filter(function(k){return data.items[k]}); } catch(e) { chosen=[]; }
  function save(){ try { localStorage.setItem(data.store, JSON.stringify(chosen)); } catch(e) {} }
  function build(){ return data.header + chosen.map(function(k){return data.items[k]}).join('') + data.footer; }
  function show(open){ opened=open; body.hidden=!open; tog.setAttribute('aria-expanded', String(open)); bar.classList.toggle('open', open); pad(); }
  function pad(){ page.style.paddingBottom = bar.hidden ? '' : (bar.offsetHeight + 32) + 'px'; }
  function sync(){
    buttons.forEach(function(b){ var on=chosen.indexOf(b.dataset.key)>=0; b.hidden=false;
      b.setAttribute('aria-pressed', String(on)); b.querySelector('.add-word').textContent = on ? 'On the fix list' : 'Add to fix list'; });
    count.textContent = chosen.length + (chosen.length===1 ? ' item' : ' items');
    bar.hidden = chosen.length===0;
    if (!chosen.length) { edited=false; show(false); }
    if (!edited) ta.value = build();
    pad();
  }
  function flip(key){
    var i=chosen.indexOf(key), part=data.items[key];
    if (i<0) { chosen.push(key);
      if (edited) { var at = data.footer ? ta.value.lastIndexOf(data.footer) : -1;
        ta.value = at<0 ? ta.value + part : ta.value.slice(0,at) + part + ta.value.slice(at); }
    } else { chosen.splice(i,1); if (edited) ta.value = ta.value.replace(part, ''); }
    save(); sync();
  }
  buttons.forEach(function(b){ b.addEventListener('click', function(){ flip(b.dataset.key); }); });
  tog.addEventListener('click', function(){ show(!opened); });
  ta.addEventListener('input', function(){ edited=true; });
  el('fb-clear').addEventListener('click', function(){ chosen=[]; save(); sync(); });
  function say(text){ status.textContent=text; clearTimeout(timer); timer=setTimeout(function(){ status.textContent=''; copy.textContent='Copy prompt'; }, 4000); }
  function fallback(){
    if (!opened) show(true);
    ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length);
    var ok=false; try { ok=document.execCommand('copy'); } catch(e) { ok=false; }
    if (ok) { copy.textContent='Copied'; say('Copied. Paste it into Claude Code.'); }
    else say('The text is selected. Press Cmd+C or Ctrl+C to copy it.');
  }
  copy.addEventListener('click', function(){
    var text=ta.value;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function(){ copy.textContent='Copied'; say('Copied. Paste it into Claude Code.'); }, fallback);
        return;
      }
    } catch(e) {}
    fallback();
  });
  window.addEventListener('resize', pad);
  sync();
})();
"""

CSS = r"""
/* Layout: one calm column that answers "did it work?" top to bottom; builder detail closed at the end.
   2X: black ground, Inter, one red. Colour is spent on state only. Dark first, with the 2X light inversion. */
:root{
  --bg:#000;--surface:#121212;--raised:#262626;--line:#2e2e2e;--fg:#fff;--fg-soft:rgba(255,255,255,.86);--muted:#a2a2a2;
  --pass:#00cc99;--pass-bg:rgba(0,204,153,.13);--fail:#ff4747;--fail-bg:rgba(255,71,71,.14);
  --warn:#ffd24a;--warn-bg:rgba(255,210,74,.13);--idle:#8a8a8a;--idle-bg:#262626;--focus:#ff0f0f;
  --font:"Inter","Inter Variable",-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  color-scheme:dark;
}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){
  --bg:#fff;--surface:#f5f5f5;--raised:#ebebeb;--line:#dedede;--fg:#141414;--fg-soft:#2a2a2a;--muted:#5c5c5c;
  --pass:#00795a;--pass-bg:#e1f4ee;--fail:#c40000;--fail-bg:#fde9e9;--warn:#835800;--warn-bg:#fbf0d2;
  --idle:#767676;--idle-bg:#ececec;--focus:#e60000;color-scheme:light}}
:root[data-theme="light"]{
  --bg:#fff;--surface:#f5f5f5;--raised:#ebebeb;--line:#dedede;--fg:#141414;--fg-soft:#2a2a2a;--muted:#5c5c5c;
  --pass:#00795a;--pass-bg:#e1f4ee;--fail:#c40000;--fail-bg:#fde9e9;--warn:#835800;--warn-bg:#fbf0d2;
  --idle:#767676;--idle-bg:#ececec;--focus:#e60000;color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:400 17px/1.55 var(--font);letter-spacing:-.011em;
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
::selection{background:var(--fail);color:#fff}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px;border-radius:6px}
code{font-family:var(--mono);font-size:.84em;word-break:break-all}
small{display:block;font-size:.84rem;color:var(--muted);letter-spacing:0}
.muted{color:var(--muted)}
.page{max-width:760px;margin:0 auto;padding-block:40px 64px;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.top h1{font-size:2.5rem;font-weight:600;letter-spacing:-.03em;line-height:1.1;margin:0 0 6px;text-wrap:balance}
.sub{margin:0;color:var(--muted)}
/* the mark: a filled circle for pass, a ring with a bar for fail and warn, a hollow ring for not run */
.mark{width:18px;height:18px;border-radius:50%;flex:none;display:inline-block;position:relative;margin-top:.22em;
  border:2px solid var(--idle);background:transparent}
.mark--pass{background:var(--pass);border-color:var(--pass)}
.mark--pass::after{content:"";position:absolute;left:5px;top:1.5px;width:4px;height:8px;border:solid var(--bg);
  border-width:0 2px 2px 0;transform:rotate(45deg)}
.mark--fail{background:var(--fail);border-color:var(--fail)}
.mark--fail::after,.mark--warn::after{content:"";position:absolute;left:6px;top:2px;width:2px;height:7px;background:var(--bg);border-radius:1px}
.mark--warn{background:var(--warn);border-color:var(--warn)}
/* verdict */
.verdict{margin-top:28px;background:var(--surface);border-radius:24px;padding:26px 28px}
.verdict-word{display:flex;align-items:center;gap:12px;margin:0;font-size:2rem;font-weight:600;letter-spacing:-.025em;line-height:1.15}
.verdict-word .mark{width:24px;height:24px;margin-top:0}
.verdict-word .mark--pass::after{left:7px;top:3px;width:5px;height:10px}
.verdict-word .mark--fail::after,.verdict-word .mark--warn::after{left:9px;top:4px;height:9px}
.verdict--pass .verdict-word{color:var(--pass)}.verdict--warn .verdict-word{color:var(--warn)}.verdict--fail .verdict-word{color:var(--fail)}
.verdict-why{margin:12px 0 0;font-size:1.15rem;line-height:1.5;max-width:60ch}
.verdict-block{margin:10px 0 0;color:var(--fail)}
.verdict-conf{margin:14px 0 0;color:var(--muted);font-size:.92rem}
/* sections */
.sec{margin-top:44px}
.sec h2{font-size:1.3rem;font-weight:600;letter-spacing:-.02em;margin:0 0 14px}
.ok{margin:0;color:var(--fg-soft)}
.note{margin:10px 0 0;color:var(--muted);font-size:.9rem}
.checklist,.lines,.fixes{list-style:none;margin:0;padding:0}
.checklist li{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:14px;align-items:start;padding:12px 0;
  border-top:1px solid var(--line)}
.checklist li:last-child{border-bottom:1px solid var(--line)}
.ck-text b{display:block;font-weight:600}
.ck-text span{display:block;color:var(--fg-soft);font-size:.95rem}
.ck-word{font-size:.88rem;font-weight:600;white-space:nowrap;color:var(--muted)}
.ck-word--pass{color:var(--pass)}.ck-word--fail{color:var(--fail)}
.lines{display:grid;gap:10px}
.lines li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:14px;align-items:start}
.fx-group+.fx-group{margin-top:22px}
.fx-group h3{margin:0 0 10px;font-size:1rem;font-weight:600;color:var(--muted)}
.fixes{display:grid;gap:10px}
.fixes li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:14px;align-items:start;background:var(--surface);
  border-radius:16px;padding:14px 16px}
.fx-text>*{display:block}
.fx-text b{font-weight:600;margin-bottom:4px}
.fx-text span{color:var(--fg-soft);font-size:.95rem}
.lbl{color:var(--muted)}
/* details for builders */
.details{margin-top:56px;border-top:1px solid var(--line);padding-top:6px}
.details>summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:10px;font-weight:600;padding:10px 0;color:var(--muted)}
.details>summary::-webkit-details-marker{display:none}
.details>summary::after{content:"";width:8px;height:8px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);
  transform:rotate(45deg);transition:transform .15s}
.details[open]>summary::after{transform:rotate(-135deg)}
.dt-body{font-size:.9rem}
.dt-block{margin-top:26px}
.dt-block h3{font-size:1rem;font-weight:600;margin:0 0 10px}
.dt-block p{margin:0 0 8px;max-width:75ch}
.kv{margin:0;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.kv dt{font-size:.8rem;color:var(--muted)}
.kv dd{margin:0;overflow-wrap:anywhere}
.chip{display:inline-flex;white-space:nowrap;border-radius:999rem;padding:1px 9px;font-size:.76rem;font-weight:600;
  background:var(--idle-bg);color:var(--fg-soft)}
.chip--pass{background:var(--pass-bg);color:var(--pass)}.chip--fail{background:var(--fail-bg);color:var(--fail)}
.chip--warn{background:var(--warn-bg);color:var(--warn)}
.dt-block .lines li{grid-template-columns:auto minmax(0,1fr)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:.84rem}
th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:.76rem;background:var(--surface)}
td.num{color:var(--muted);white-space:nowrap}
tr:last-child td{border-bottom:0}
.track{position:relative;height:50px;margin:8px 8px 18px}
.rail{position:absolute;left:0;right:0;top:26px;height:2px;background:var(--line)}
.tick{position:absolute;top:20px;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:var(--idle);box-shadow:0 0 0 3px var(--bg)}
.tick--pass{background:var(--pass)}.tick--fail{background:var(--fail)}.tick--warn{background:var(--warn)}
.limit{position:absolute;top:6px;bottom:6px;border-left:2px dashed var(--muted)}
.limit span{position:absolute;right:6px;top:-6px;font-size:.72rem;color:var(--muted);white-space:nowrap}
.tl{list-style:none;margin:0 0 8px;padding:0;display:grid;gap:10px}
.tl li{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:12px;align-items:start}
.tl-when{text-align:right;white-space:nowrap;font-weight:600}
.tl-when small{font-weight:400}
/* the fix list: a toggle on each fix, a bar fixed to the bottom that opens to the prompt */
.add{margin-top:10px;display:inline-flex;align-items:center;gap:8px;font:600 .88rem/1 var(--font);letter-spacing:0;
  color:var(--fg);background:transparent;border:1px solid var(--line);border-radius:999rem;padding:8px 14px 8px 10px;cursor:pointer}
.add[hidden]{display:none}
.fx-text .add span{color:inherit;font-size:inherit}
.add:hover{border-color:var(--muted)}
.add-plus{width:16px;height:16px;border-radius:50%;border:1.5px solid currentColor;position:relative;flex:none}
.add-plus::before,.add-plus::after{content:"";position:absolute;left:50%;top:50%;width:8px;height:1.5px;background:currentColor;
  transform:translate(-50%,-50%)}
.add-plus::after{transform:translate(-50%,-50%) rotate(90deg)}
.add[aria-pressed="true"]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.add[aria-pressed="true"] .add-plus{background:var(--bg);border-color:var(--bg)}
.add[aria-pressed="true"] .add-plus::before{width:3px;height:6px;background:transparent;border:solid var(--fg);border-width:0 1.5px 1.5px 0;
  transform:translate(-50%,-62%) rotate(45deg)}
.add[aria-pressed="true"] .add-plus::after{display:none}
.fixbar{position:fixed;left:0;right:0;bottom:0;z-index:20;
  padding:0 max(16px,env(safe-area-inset-right,0px)) calc(12px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px))}
.fixbar[hidden]{display:none}
.fb-in{max-width:760px;margin:0 auto;background:var(--raised);border:1px solid var(--line);border-radius:20px;padding:10px 10px 10px 16px;
  box-shadow:0 12px 40px rgba(0,0,0,.35)}
.fb-head{display:flex;align-items:center;gap:10px}
.fb-toggle{flex:1;min-width:0;display:flex;align-items:center;gap:8px;background:none;border:0;color:var(--fg);font:400 1rem var(--font);
  padding:6px 0;cursor:pointer;text-align:left}
.fb-toggle span{color:var(--muted)}
.fb-chev{width:8px;height:8px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(-135deg);
  margin-left:4px;transition:transform .15s}
.fixbar.open .fb-chev{transform:rotate(45deg)}
.fb-copy{flex:none;font:600 .95rem/1 var(--font);color:#fff;background:var(--focus);border:0;border-radius:999rem;padding:12px 18px;cursor:pointer}
.fb-body{padding:6px 6px 4px 0}
.fb-body[hidden]{display:none}
.fb-label{display:block;font-size:.85rem;color:var(--muted);margin:4px 0 8px}
.fb-body textarea{width:100%;min-height:200px;max-height:45vh;resize:vertical;background:var(--bg);color:var(--fg);border:1px solid var(--line);
  border-radius:12px;padding:12px;font:400 .82rem/1.5 var(--mono)}
.fb-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px}
.fb-status{font-size:.85rem;color:var(--pass);min-height:1.2em}
.fb-clear{background:none;border:0;color:var(--muted);font:400 .85rem var(--font);text-decoration:underline;cursor:pointer;padding:6px 0}
@media (max-width:560px){
  .top h1{font-size:2rem}
  .verdict{padding:22px}
  .verdict-word{font-size:1.65rem}
  .checklist li{grid-template-columns:18px minmax(0,1fr)}
  .ck-word{grid-column:2;margin-top:-6px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

if __name__ == "__main__":
    main()
