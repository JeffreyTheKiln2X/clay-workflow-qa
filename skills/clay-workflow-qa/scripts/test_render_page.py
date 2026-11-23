"""Tests for render_page.py. Run from the repo root:

    python3 -I skills/clay-workflow-qa/scripts/test_render_page.py
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_page as rp  # noqa: E402

ZERO = {"data": 0, "action": 0}


def dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f)


def read(path):
    with open(path) as f:
        return f.read()


def base():
    """The smallest results file that draws: every step passed in this run, one rule, one record, one trigger."""
    steps = [{"id": i, "result": "PASS", "bar": "bar %s" % i, "proof": "proof %s" % i,
              "plain": "Plain line %s." % i, "credits": dict(ZERO)}
             for i in rp.STEP_IDS]
    steps[5] = {"id": "e", "result": "SKIPPED", "why": "The play is live.", "credits": dict(ZERO)}
    return {
        "schema": 1, "play": "Test Play", "date": "2026-11-19", "run_label": "First run", "ran_by": "Sam",
        "target": "The play itself", "verdict": {"why": "It did what the doc says."}, "credits": {"limit": 20},
        "steps": steps,
        "rules": [{"n": "1", "rule": "An open deal ends out", "test": "unit case", "expected": "out", "actual": "out",
                   "result": "PASS"}],
        "records": [{"name": "Acme", "why": "Should go all the way", "expected": "staged", "actual": "staged", "equal": True,
                     "line": "Acme: would have emailed 2 people, as expected."}],
        "trigger": {"limit_minutes": 90, "events": [{"label": "Entered", "at": "2026-11-19T10:00:00Z"},
                                                     {"label": "Run started", "at": "2026-11-19T10:40:00Z"},
                                                     {"label": "Cleaned up"}]},
        "alerts": [],
        "cleanup": [{"part": "Test account", "proof": "0 left", "gone": True}],
    }


class Check(unittest.TestCase):
    def test_base_has_no_gaps(self):
        self.assertEqual(rp.check(base()), [])

    def test_missing_step_is_a_gap(self):
        d = base()
        d["steps"] = d["steps"][:-1]
        self.assertTrue(any("steps" in g for g in rp.check(d)))

    def test_skipped_step_needs_a_reason(self):
        d = base()
        del d["steps"][5]["why"]
        self.assertTrue(any("step e" in g and "why" in g for g in rp.check(d)))

    def test_passed_step_needs_bar_and_proof(self):
        d = base()
        del d["steps"][1]["bar"]
        self.assertTrue(any("step a" in g and "bar" in g for g in rp.check(d)))

    def test_smoke_ran_needs_records(self):
        d = base()
        d["records"] = []
        self.assertTrue(any(g.startswith("records") for g in rp.check(d)))

    def test_trigger_ran_needs_timeline(self):
        d = base()
        d["trigger"] = None
        self.assertTrue(any(g.startswith("trigger") for g in rp.check(d)))

    def test_cleanup_needs_list_or_reason(self):
        d = base()
        d["cleanup"] = []
        self.assertTrue(any(g.startswith("cleanup") for g in rp.check(d)))
        d["cleanup_none"] = "Only free code tests ran; nothing was made."
        self.assertEqual(rp.check(d), [])

    def test_alert_fields(self):
        d = base()
        d["alerts"] = [{"key": "k", "title": "t", "severity": "urgent", "status": "open", "kind": "alert"}]
        gaps = rp.check(d)
        self.assertTrue(any("severity" in g for g in gaps))
        self.assertTrue(any("`why`" in g for g in gaps))

    def test_passed_step_needs_a_plain_line(self):
        d = base()
        del d["steps"][2]["plain"]
        self.assertTrue(any("step b" in g and "plain" in g for g in rp.check(d)))

    def test_record_needs_a_line(self):
        d = base()
        del d["records"][0]["line"]
        self.assertTrue(any("record Acme" in g and "line" in g for g in rp.check(d)))

    def test_builder_words_above_the_fold_are_gaps(self):
        d = base()
        d["verdict"]["why"] = "The dry run passed and the trigger fired."
        d["records"][0]["line"] = "Acme: EMAIL_NOT_VALID on node 4."
        d["alerts"] = [{"key": "k", "kind": "alert", "severity": "high", "status": "open", "title": "Publish wf_0abc",
                        "why": "The segment and the trigger are fine here: why sits in the details.",
                        "fix": "Fix the status column.", "decides": "Owner"}]
        gaps = rp.check(d)
        self.assertTrue(any(g.startswith("verdict.why") and "dry run" in g and "trigger" in g for g in gaps))
        self.assertTrue(any("record Acme line" in g and "reason code" in g and "node" in g for g in gaps))
        self.assertTrue(any("title" in g and "Clay id" in g for g in gaps))
        self.assertTrue(any("fix" in g and "status column" in g for g in gaps))
        self.assertFalse(any("why" in g and "alert" in g for g in gaps))

    def test_closed_alert_may_keep_builder_words(self):
        d = base()
        d["alerts"] = [{"key": "k", "kind": "alert", "severity": "high", "status": "ruled", "title": "The trigger list",
                        "why": "w", "fix": "f", "decides": "Owner"}]
        self.assertEqual(rp.check(d), [])

    def test_bad_time_is_a_gap(self):
        d = base()
        d["trigger"]["events"][0]["at"] = "ten o'clock"
        self.assertTrue(any("ISO" in g for g in rp.check(d)))


class Reads(unittest.TestCase):
    def test_ready_and_high(self):
        d = base()
        self.assertEqual(rp.verdict(d), "ready")
        self.assertEqual(rp.confidence(d), "high")

    def test_open_alert_is_fix_first(self):
        d = base()
        d["alerts"] = [{"key": "k", "kind": "alert", "severity": "high", "status": "open", "title": "t", "why": "w",
                        "fix": "f", "decides": "Owner"}]
        self.assertEqual(rp.verdict(d), "fix")
        d["alerts"][0]["status"] = "ruled"
        self.assertEqual(rp.verdict(d), "ready")

    def test_open_finding_does_not_stop_go_live(self):
        d = base()
        d["alerts"] = [{"key": "k", "kind": "finding", "severity": "low", "status": "open", "title": "t", "why": "w",
                        "fix": "f", "decides": "Owner"}]
        self.assertEqual(rp.verdict(d), "ready")

    def test_failed_step_is_fix_first_and_low(self):
        d = base()
        d["steps"][2]["result"] = "FAIL"
        self.assertEqual(rp.verdict(d), "fix")
        self.assertEqual(rp.confidence(d), "low")

    def test_rule_with_no_test_is_low(self):
        d = base()
        d["rules"].append({"n": "2", "rule": "money skip", "expected": "out", "result": "NO TEST"})
        self.assertEqual(rp.verdict(d), "fix")
        self.assertEqual(rp.confidence(d), "low")

    def test_record_not_equal_is_fix_first(self):
        d = base()
        d["records"][0]["equal"] = False
        self.assertEqual(rp.verdict(d), "fix")

    def test_carried_step_is_medium(self):
        d = base()
        d["steps"][3]["from"] = "the first run"
        self.assertEqual(rp.confidence(d), "medium")
        self.assertEqual(rp.verdict(d), "ready")

    def test_blocked(self):
        d = base()
        d["blocked"] = {"reason": "the play doc is thin", "decides": "the play owner"}
        self.assertEqual(rp.verdict(d), "blocked")
        self.assertEqual(rp.confidence(d), "low")


class Compare(unittest.TestCase):
    def test_nothing_changed(self):
        self.assertEqual(rp.compare(base(), base()), [])

    def test_new_fail_fixed_rule_and_closed_alert(self):
        prev, cur = base(), base()
        prev["rules"].append({"n": "2", "rule": "money skip", "expected": "out", "result": "NO TEST"})
        cur["rules"].append({"n": "2", "rule": "money skip", "expected": "out", "test": "t", "actual": "out", "result": "PASS"})
        prev["alerts"] = [{"key": "a1", "kind": "alert", "severity": "high", "status": "open", "title": "Old alert",
                           "why": "w", "fix": "f", "decides": "Owner"}]
        cur["steps"][1]["result"] = "FAIL"
        out = rp.compare(cur, prev)
        kinds = {t: k for k, t in out}
        self.assertEqual(kinds.get("Static check: was passed, now failed."), "new")
        self.assertEqual(kinds.get("Rule 2, money skip: was no test, now proven."), "fixed")
        self.assertEqual(kinds.get("Closed: Old alert"), "fixed")


class Draw(unittest.TestCase):
    def test_simple_sections_and_no_outside_calls(self):
        d = base()
        d["ids"] = [{"label": "Run", "value": "wfr_123"}]
        page = rp.render(d)
        for sid in ("checked", "accounts", "fix", "not-tested", "details"):
            self.assertIn('id="%s"' % sid, page)
        for name in ("Listed every rule in the play doc", "Tried it on real accounts without sending", "Cleaned up"):
            self.assertIn(name, page)
        self.assertIn("Ready to go live", page)
        self.assertIn("High confidence", page)
        self.assertNotRegex(page, r'(src|href)="https?://')
        self.assertNotIn("@import", page)
        self.assertNotRegex(page, r"<script[^>]*src=")

    def test_builder_detail_sits_in_the_closed_section(self):
        d = base()
        d["ids"] = [{"label": "Run", "value": "wfr_secret_id"}]
        page = rp.render(d)
        fold = page.index('<details class="details" id="details">')
        self.assertNotIn("<details open", page)
        for detail in ("wfr_secret_id", "Pass bar, set before the run", "Rules of the play doc", "Trigger test timeline",
                       "credit limit", "Compared to the last run", "Credits (data, action)", "Doc line"):
            self.assertGreater(page.index(detail), fold, detail)
        top = page[:fold]
        for word in ("Trigger", "Dry run", "Segment", "Credit"):
            self.assertNotIn(word, top.split("</style>")[-1])

    def test_one_line_a_record(self):
        page = rp.render(base())
        fold = page.index('id="details"')
        self.assertLess(page.index("Acme: would have emailed 2 people, as expected."), fold)

    def test_open_alert_shows_what_to_do_and_who_decides(self):
        d = base()
        d["alerts"] = [{"key": "k", "kind": "alert", "severity": "high", "status": "open", "title": "Approve the new version",
                        "why": "w", "fix": "Say yes to it.", "decides": "Owner"},
                       {"key": "f", "kind": "finding", "severity": "low", "status": "open", "title": "A note is stale",
                        "why": "w", "fix": "Reword it.", "decides": "2X"}]
        page = rp.render(d)
        top = page[:page.index('id="details"')]
        self.assertIn("Before it goes live", top)
        self.assertIn("Can wait", top)
        self.assertIn("Who decides:</span> Owner", top)

    def test_not_tested_lists_skipped_and_carried_steps(self):
        d = base()
        d["steps"][3]["from"] = "the first run"
        page = rp.render(d)
        sec = page[page.index('id="not-tested"'):page.index('id="details"')]
        self.assertIn("Sent for real on one account", sec)
        self.assertIn("Tried it on real accounts without sending", sec)

    def test_text_is_escaped(self):
        d = base()
        d["records"][0]["actual"] = "<b>staged</b> & sent"
        page = rp.render(d)
        self.assertIn("&lt;b&gt;staged&lt;/b&gt; &amp; sent", page)

    def test_fragment_has_no_document_shell(self):
        frag = rp.render(base(), fragment=True)
        self.assertTrue(frag.startswith("<title>"))
        self.assertNotIn("<!doctype", frag.lower())
        self.assertNotIn("<body", frag)

    def test_both_themes(self):
        page = rp.render(base())
        self.assertIn("prefers-color-scheme: light", page)
        self.assertIn(':root[data-theme="light"]', page)


def open_items():
    return [{"key": "publish", "kind": "alert", "severity": "high", "status": "open", "title": "The new rule is not live yet",
             "why": "The trigger still sends to the rotation.", "fix": "Approve putting it live.", "decides": "Owner",
             "record": "wfr_123 on the draft", "rules": ["1"]},
            {"key": "note", "kind": "finding", "severity": "low", "status": "open", "title": "A note is stale",
             "why": "w", "fix": "Reword it.", "decides": "2X"},
            {"key": "old", "kind": "alert", "severity": "high", "status": "ruled", "title": "Settled",
             "why": "w", "fix": "f", "decides": "Owner (ruled)"}]


class FixList(unittest.TestCase):
    def test_a_toggle_for_each_open_item_only(self):
        d = base()
        d["alerts"] = open_items()
        page = rp.render(d)
        self.assertEqual(len(re.findall(r'<button type="button" class="add" data-key="(publish|note)" aria-pressed="false" hidden>', page)), 2)
        self.assertNotIn('data-key="old"', page)
        self.assertIn('id="fixbar"', page)

    def test_no_fix_list_when_nothing_is_open(self):
        page = rp.render(base())
        self.assertNotIn('id="fixbar"', page)
        self.assertNotIn("<script", page)

    def test_the_prompt(self):
        d = base()
        d["alerts"] = open_items()
        d["report"] = "2026-11-19-qa.md"
        d["_file"] = "qa/demo/tests/2026-11-19-qa.json"
        d["ids"] = [{"label": "Live workflow", "value": "wf_abc"}]
        fp = rp.fix_prompt(d)
        self.assertIn("Fix list from the Test Play test of 2026-11-19 (First run).", fp["header"])
        self.assertIn("Report: qa/demo/tests/2026-11-19-qa.md.", fp["header"])
        self.assertIn("run Skill(clay-workflow-qa) on Test Play again", fp["header"])
        self.assertEqual(sorted(fp["items"]), ["note", "publish"])
        item = fp["items"]["publish"]
        for part in ("- The new rule is not live yet", "Kind: alert, high severity, stops go live. Key: publish.",
                     "What to do: Approve putting it live.", "Who decides: Owner", "Why: The trigger still sends",
                     "Record: wfr_123 on the draft", "Rule 1: An open deal ends out", "Expected: out"):
            self.assertIn(part, item)
        self.assertIn("- Live workflow: wf_abc", fp["footer"])

    def test_builder_words_are_fine_in_the_prompt_only(self):
        d = base()
        d["alerts"] = open_items()
        self.assertEqual(rp.check(d), [])
        d["alerts"][0]["fix"] = "Publish the workflow."
        self.assertTrue(any("fix" in g and "workflow" in g for g in rp.check(d)))

    def test_alert_rules_must_exist(self):
        d = base()
        d["alerts"] = open_items()
        d["alerts"][0]["rules"] = ["99"]
        self.assertTrue(any("rule 99" in g for g in rp.check(d)))

    def test_prompt_data_survives_a_closing_tag(self):
        d = base()
        d["alerts"] = open_items()
        d["alerts"][0]["why"] = "A </script> in the text"
        page = rp.render(d)
        raw = re.search(r'<script type="application/json" id="fix-data">(.*?)</script>', page, re.S).group(1)
        self.assertIn("A </script> in the text", json.loads(raw)["items"]["publish"])

    def test_copy_has_a_fallback_and_storage_is_guarded(self):
        js = rp.JS
        self.assertIn("navigator.clipboard.writeText(text).then(", js)
        self.assertIn("fallback);", js)
        self.assertIn("ta.select();", js)
        self.assertIn("document.execCommand('copy')", js)
        self.assertIn("Press Cmd+C or Ctrl+C", js)
        self.assertIn("Copied", js)
        self.assertRegex(js, r"try \{ chosen=JSON\.parse\(localStorage\.getItem")
        self.assertRegex(js, r"try \{ localStorage\.setItem")

    def test_toggle_flips_and_relabels(self):
        js = rp.JS
        self.assertIn("aria-pressed", js)
        self.assertIn("'On the fix list' : 'Add to fix list'", js)
        self.assertIn("chosen.splice(i,1)", js)


class Cli(unittest.TestCase):
    def run_cli(self, d, prev=None):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "2026-11-19-qa.json")
        if prev is not None:
            dump(prev, os.path.join(tmp, "prev.json"))
            d["previous"] = "prev.json"
        dump(d, path)
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(rp.__file__), "render_page.py"), path],
                           capture_output=True, text=True)
        return r, os.path.join(tmp, "2026-11-19-qa.html")

    def test_draws_the_page(self):
        r, out = self.run_cli(base(), prev=base())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(out))
        self.assertIn("Nothing changed.", read(out))

    def test_gap_stops_with_no_page(self):
        d = base()
        del d["verdict"]
        r, out = self.run_cli(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gaps", r.stderr)
        self.assertFalse(os.path.exists(out))

    def test_missing_previous_stops(self):
        d = base()
        d["previous"] = "nope.json"
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "x.json")
        dump(d, path)
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(rp.__file__), "render_page.py"), path],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
