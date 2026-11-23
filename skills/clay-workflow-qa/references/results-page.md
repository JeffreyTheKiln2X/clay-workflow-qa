# The results file and the page

Every run writes one **results file** next to its markdown report, with the same stem:
`<target folder>/tests/<date>-test-play.json` beside `<date>-test-play.md` (a second run the same day takes the
report's own stem, for example `2026-11-19-rule-19.json`). `scripts/render_page.py` draws it as one page,
`<same stem>.html`: no outside calls, light and dark, phone width, one small inline script for the fix list. Write the file; never write or edit
the page by hand, so every run looks the same.

## Who reads the page

Someone who does not build workflows: the client's team, the owner. The page answers one question, "did it
work?". Keep it simple to follow and not technical. Write every text that shows above the fold the way a
non-builder would say it: plain everyday words, one idea a sentence, the business's own names for things (the
account owner, the sales rotation, the CRM, the sequencing tool).

**Above the fold**, in this order:

1. The verdict, with the one sentence `verdict.why`.
2. **What we checked**: a checklist, one row a step with its plain name, its `plain` line and Passed or not, then
   a computed "Cleaned up" row.
3. **What the test accounts did**: one `line` a record.
4. **What needs fixing**: the open alerts under "Before it goes live", the open findings under "Can wait",
   each with its `title`, "What to do" (`fix`) and "Who decides" (`decides`).
5. **Not tested**: steps skipped, not run or carried from an earlier run, and rules with no test of their own.

**The fix list.** Each open alert and finding has an "Add to fix list" toggle (click again to remove). The
chosen items fill a box fixed to the bottom of the page: a ready Claude Code prompt the reader can edit and copy
(so the reader can paste it straight into Claude Code). `fix_prompt()` writes it: the play, the
date, the report and results file paths, a rerun of `Skill(clay-workflow-qa)` after the fixes, then each chosen item
with its title, kind, key, what to do, who decides, why, record and the rows of its `rules`, then the run's
`ids`. Builder words belong in the prompt; the plain-words gate reads only the page. The page keeps the chosen
items per viewer in the browser, so they survive a reload. Copy uses the clipboard, and selects the text with a
"press Cmd+C" line when the clipboard is blocked.

**Details for builders**, one closed section at the end: the pass bars and proofs, the rules table, the record
table, the trigger timeline, every alert with its why, credits, the cleanup read back, the compare with the last
run, and the ids. Builder words, Clay ids, reason codes and costs belong here only.

**The plain-words gate.** `render_page.py` treats a builder word in an above-the-fold text as a gap, and draws no
page: segment, trigger, node, status column, dry run, workflow, snapshot, webhook, credit, Clay, a Clay id
(`wf_`, `wfr_`, `audseg_`), a reason code (`EMAIL_NOT_VALID`), a backtick, a segment code (`(i)`) or a doc line
(`S:45`). Say what it means instead: "the list that starts the play", "a test run that sends nothing", "the
account check". The gate reads `verdict.why`, each step's `plain` or `why`, each record's `line`, and the
`title`, `fix` and `decides` of each open alert or finding. Every other field sits in the details and may use
builder words.

## The fields

Every field below is required unless it says optional. `render_page.py` checks them first and stops with every
gap listed; a gap means no page.

| Field | What it holds |
|---|---|
| `schema` | `1` |
| `play`, `date` | The play's name as people say it; the run date, `YYYY-MM-DD` |
| `run_label` | A short name for this run: "First run", "Rule 19 ruled" |
| `ran_by`, `target` | Who ran it; what was tested, in one sentence ("A test copy of the live play; the live play was not touched") |
| `report` | The markdown report's file name |
| `previous` | Optional. The file name of the play's last results file, in the same folder. The details list what changed |
| `verdict.why` | One plain sentence: what the play did and what stands between it and go live |
| `blocked` | Optional. `{reason, decides}` when the run stopped before the end (a thin doc, no yes). The verdict is then Blocked |
| `credits.limit` | The credit limit of this session (set per target: `credit_limit` in the targets file, default 20) |
| `steps` | Seven rows, ids `0`, `a`, `b`, `c`, `d`, `e`, `f`, in order (below) |
| `rules` | One row per rule of the coverage table (below). Empty only when step 0 did not run |
| `records`, `records_from` | One row per smoke and trigger record (below); optional `records_from` says which run they come from |
| `trigger` | The trigger test timeline (below), or `null` when step d did not run |
| `alerts` | Every alert and finding of the report (below). Empty when there are none |
| `cleanup`, `cleanup_from` | One row per part the test made, `{part, proof, gone}`; or `cleanup_none`: why nothing was made |
| `ids` | Optional. `[{label, value}]`: every id a builder needs to trace the run |

**A step:** `{id, result, credits: {data, action}}` plus, for `PASS` or `FAIL`, `bar` (the pass bar written before
the run), `proof` (what it showed, with counts) and `plain` (the proof in one plain sentence: "5 real accounts
went through without sending. Each did what the doc says"); for `SKIPPED` or `NOT RUN`, `why` (plain). A step
shown from an earlier run keeps that run's result and adds `from` ("the first run today, 10:42 to 12:00 UTC").
Credits are what the step spent then. The checklist names each step for the reader:

| id | Builder name (details) | Checklist name |
|---|---|---|
| 0 | Spec | Listed every rule in the play doc |
| a | Static check | Checked the setup matches the doc |
| b | Step tests | Tested each decision the play makes |
| c | Dry run smoke | Tried it on real accounts without sending |
| d | Trigger test | Let it start by itself on a test account |
| e | Canary | Sent for real on one account |
| f | Review | Looked for problems and improvements |

**A rule:** `{n, rule, doc_line, test, expected, actual, result}`. `result` is `PASS`, `FAIL`, `NO TEST` (no
`test` or `actual` then) or `MODULE` (proven only in a shared part). `expected` comes from the doc.

**A record:** `{name, why, expected, actual, equal, line}`, optional `note`. `name` is the company or "Trigger test
account"; `why` is why it was picked; `expected` is what the doc predicts; `actual` is what the run wrote
(status, reason, people, would-do lines); `equal` is `true`, `false` or `null` (not compared). `line` is the one
plain line the page shows: "Agiliti: would have emailed 2 people, and nothing was sent, as expected."

**The trigger:** `{events, limit_minutes, summary, from}`. Each event `{label, at, note, state}`: `at` is an ISO
time in UTC (leave it out when it was not recorded), `state` is `pass` (default), `fail` or `warn`. Give the
entry, the run start, the status read back, the exit from the trigger list and the cleanup. The first timed
event is minute 0.

**An alert or finding:** `{key, kind, severity, status, title, why, fix, decides}`, optional `record` and
`rules` (the rule numbers it touches, so the fix list prompt carries those rows). `kind` is
`alert` (an alert of the report: it stops go live while open) or `finding` (it does not). `severity` is `high`
(can send a wrong email or lose a record), `medium` or `low`. `status` is `open`, `ruled` (the owner ruled; the
quote and date in `why`) or `fixed`. `key` stays the same from run to run for the same issue, so the details can
say what closed. `title` says what is wrong in plain words; `fix` is what to do; `decides` is who says yes. `why`,
`record` and `rules` sit in the details and in the fix list prompt.

## What the page computes

The page draws the verdict and the confidence level from the fields, so the agent cannot word them up.

| Verdict | When |
|---|---|
| Blocked | `blocked` is set |
| Fix first | A step failed, a rule is not `PASS`, an alert is open, or a record is not equal |
| Ready to go live | Otherwise |

| Confidence | When |
|---|---|
| Low | Blocked, a step failed, or a rule failed or has no test |
| High | Steps 0 to d all passed in this run (none shown from an earlier run) |
| Medium | Otherwise: nothing failed, but a step was carried or did not run |

## Draw and show

```
python3 skills/clay-workflow-qa/scripts/render_page.py <results file> --fragment <scratchpad>/<stem>.html
```

It writes `<stem>.html` next to the results file and prints the verdict. `--fragment` writes the same page
without its document shell, for the Artifact tool. Then show it:

- **The Artifact tool exists:** load `Skill(artifact-design)`, publish the fragment as a private Artifact
  (icon `checklist`, one Artifact per run), and put the link in the reply.
- **Else:** open the local page (`open <stem>.html`) and name its path in the reply.

The tests: `python3 skills/clay-workflow-qa/scripts/test_render_page.py`.
