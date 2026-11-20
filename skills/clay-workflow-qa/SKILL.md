---
name: clay-workflow-qa
description: "QA an existing Clay workflow the way a senior web QA tests an app: safety gate, map, plan with pass bars, cheapest tests first, verified runs, bug reports, sign-off report. Use when someone asks to QA, test, audit or check a Clay workflow (a play, a module, any wf_ id), or to find bugs in one."
---

# Clay workflow QA

Act as a **senior QA engineer** on a Clay workflow. The draft is your **staging**, the published version is **production**. You test on staging, you change nothing in production, and every finding comes with evidence (a run id, a count, a before/after diff).

Works on any Clay workflow, with no repo needed. Needs: the Clay CLI logged in to the right workspace (`clay whoami` shows it) and read access to the workflow, its runs and Audiences. Where results go is the user's choice (a local test log file and a sheet by default).

How each web QA practice maps to Clay: [`references/web-qa-map.md`](references/web-qa-map.md). CLI commands and gotchas for every step below: [`references/clay-cli-recipes.md`](references/clay-cli-recipes.md).

## Hard rules

- **The client's CRM and their people stay untouched, always.** Every test run keeps CRM writes (Salesforce, HubSpot, any CRM) and outbound messages (Slack, email, campaign or sequence enrollment) off or in dry run, including runs where an Audiences write was approved. Off means the step does not send. Pointing it at a test channel, inbox or webhook still sends, so it counts as on: allowed only when the owner approved that target and no one from the client can see it. Check each one is off before every run and absent after it (step 7). These are the writes the client sees and nobody can take back. Turning one on is outside QA: it needs the owner's yes and the client's yes, in writing.
- **A write needs a yes to that write.** "Test it" or "run it" is not a yes to writing. Before any run, say in plain words what it would write, where, and that Audiences values cannot be cleared; then wait.
- **Approved test writes go on known real records.** Pick 2 or 3 records already seen in past runs, and write to test or status fields where the workflow has them, so the write runs on real data and a later run can overwrite it. Fake records rarely reach the real path (lookups find nothing), and removing them needs an Admin. Use fake records only if the owner asks, tagged plainly (name "QA TEST", domain example.com) and in their own segment, with an Admin's agreement to delete them **before** the write.
- **Staging only.** Full runs go on the draft (`clay workflows runs test` with no `--live`). The app's Run button and a manual trigger usually run the **published** version.
- **Price before you run.** State the estimate in data and action credits apart, set a stop line (estimate plus 20 percent), and report the actual after. Offer the smallest test that answers the question first: if a single-step test of one step proves it at 0 credits, lead with that and keep full runs as the follow-up. Leave out paid steps the test does not need (an enrichment after the decision being tested). Ask before anything at or over the team's credit limit.
- **Pass bars before results.** Write the expected outcome of each test before running it. A bar written after the result is a story.
- **Change only what was approved.** A fix goes into the draft only. Publishing is the owner's call.

## Steps

### 1. Safety gate
Find every way the workflow can write: Audiences update steps, Clay table row adds or updates, Salesforce or other CRM steps, Slack or email steps, HTTP or webhook calls to outside tools (n8n, Instantly, any API), campaign or sequence enrollment, steps that start another workflow, and the same inside every **called workflow** (read each called workflow's published version). Treat any step that is not clearly read-only as a write until its code or config proves otherwise.

Then map what is **downstream** of every Audiences write, because a write can set off another live workflow that sends for you. For each field and record the test could write: which segments filter on it (compare field ids), and which live triggers watch those segments (segment triggers, and `ALL` assignments that watch every record), and what those workflows do (campaign enrollment, CRM sync, messages). Fake or test data does not make this safe: the downstream workflow cannot tell it is fake. Safe options, best first: write only to fields no live segment reads; make the test records fail the segment filters (checked against the real filter); pause the downstream trigger or campaign with the owner's yes and a named person to turn it back on; or skip the write and test only up to the step before it. Find each write switch (code settings, `write_mode`, `dry_run`) and its current value in the draft and in the published version. A switch is proven only when you read the step's code or config using it; a setting name or a description saying so is a claim, so list that switch as **unverified** and treat its step as live. Note which version each trigger runs, and the guards that decide which records reach the writes (a guard that lets blanks through widens every write).

Done when: every write path is listed with how it is made safe (switch off in the draft, dry run, or a step test that stops before it), and the user has said yes to that plan. If a write cannot be made safe, test only with single-step tests (step 6a) up to the step before it.

### 2. Recon
Map the workflow: steps in order, branches and their rules, called workflows and their versions, segments and columns it reads or writes, triggers, and recent run history (count, failures, credits).

Done when: you can name every step, every branch condition, every outside dependency, and every possible end result (reason code or status).

### 3. Static review (0 credits)
Read without running. Look for: inputs into called workflows that have no source, called workflows that are not pinned (they follow the latest publish), descriptions that disagree with the code, switches that differ between draft and published, a repo or source copy that differs from live (only if one exists), segments that filter on a column the workflow does not write.

Done when: every step has been read once and each finding has evidence.

### 4. History audit (0 credits)
Mine past runs before spending anything. Pull the result step's outputs from every run (`scripts/run_audit.py`), then cross-tab fields that should agree: an early flag against the final status, a label against the final decision. Disagreement is where bugs hide.

Done when: every key output field has been cross-tabbed against the final result, and the outcome coverage so far is known (`scripts/outcome_coverage.py`).

### 5. Test plan
Build the **outcome coverage matrix**: every end result from step 2, how it was already seen (past runs), and how you will reach the rest. One record per outcome class, not many of the same.

Then build the **edge case set**. Outcome coverage alone misses these, because every outcome can pass while the edges of a rule are wrong. Go rule by rule and input by input:
- **Thresholds** (month limits, scores, counts): test exactly at the line, one below and one above. Also test what happens when the setting itself is blank.
- **Inputs each step reads** (dates, ids, URLs, domains, names): test blank, junk, the wrong format and an impossible value (a future date, a negative number).
- **Guards and filters** (region, status, already-done checks): test the blank value. A blank that passes a guard is the most common hidden gap. Also test one value that should fail.
- **Lookups** (record id, segment, called workflow): test no match, a bad id, and more than one match.
- **Fallbacks** (route defaults, "unknown" labels): test the case that triggers each one.
- **Re-runs**: run the same record twice (duplicates, double sends), and a record whose result changes between runs (a fit record that becomes not fit: do the old values stay?).

For each case, decide what *should* happen before writing the pass bar. If the right behavior is a business choice (should a blank location count as U.S.?), mark it **owner call**. Test what it does now, and report it as a question, not a bug.

Most edge cases run as single-step tests with made-up inputs (step 6a), at 0 credits for code steps. Write the pass bar for each test and the credit estimate for the whole plan.

Done when: every outcome has a planned test or a stated reason it cannot be tested; every threshold, input, guard, lookup and fallback in the workflow has its edge cases listed; and the user has approved the plan and its cost.

### 6. Execute, cheapest first
a. **Single-step tests** with made-up inputs (`clay workflows nodes test --inputs`), 0 credits for code steps: rare and error outcomes. A step test runs the step for real, so a step that can write or send is tested only after its write is switched off (proven, step 1). Inputs chosen so the write branch "should not fire" are not a safety: one wrong input sends.
b. **Smoke**: one known record, full run on the draft.
c. **One per outcome**: real records picked from history, one per class.
d. **Hard paths**: screen candidates with the cheapest gate first (a code check offline, or one called workflow alone) before paying for full runs.
e. **Regression**: after any fix, replay the changed step on past runs (`nodes test --source-run`) and rerun the smoke.

Run records that may hit a fallback or paid lookup one at a time when close to the stop line.

### 7. Verify every run
For each run: completed with 0 failed steps; the write step did not run (or wrote only what was approved); nothing changed where the workflow can write, checked per write type (Audiences: `scripts/record_diff.py snapshot` before, `compare` after; tables: row count and the touched rows' values before and after; HTTP calls, enrollments and started workflows: absent from the run's step outputs); no CRM write, no message sent; after any Audiences write, no downstream workflow ran on the test records (check the runs of each workflow mapped in step 1 for those records, and their campaigns for new enrollments); credits recorded.

Done when: every run has all five checks recorded in the test log.

### 8. Bugs
Write each bug with [`references/bug-report.md`](references/bug-report.md): severity, what happens, expected, evidence (run ids, counts), cause, proposed fix. Fix only with approval, only in the draft, snapshot first. Retest with step 6e.

Done when: each bug is reported, and each approved fix passes its regression.

**Publish check**, when the owner says yes to publishing a fix. The draft carries everything changed during QA, not only the fix: test switches turned off, edited descriptions, leftovers.
1. Run `scripts/version_diff.py <wf>` (published vs live draft). List every changed step and field in plain words for the user.
2. Match each change to an approval. The owner's yes covers the changes they were shown. Anything else (a write switch flipped for testing, a description that no longer matches the code) gets set back to the published value or asked about.
3. Set every write switch to its published value unless the owner approved a change to it. Make each step's description match its code.
4. Rerun the diff. Publish only when every remaining difference is approved, with a version name that says what changed.
5. After publishing, run `scripts/version_diff.py <wf> <old snap> <new snap>` and check the new version holds exactly the approved changes. Note which version each trigger now runs, and that the draft now equals production (switches on): turn test switches off again before any further draft run.

Done when: the new published version differs from the old one only by approved changes, and the user knows the draft's write switches are live again.

### 9. Report
Keep the test log ([`references/test-log.md`](references/test-log.md)) and one sheet row per run. End with a short owner summary: what was tested, coverage (outcomes seen of total, edge cases passed of total), bugs and their state, open questions (including every **owner call** edge case), credits, and what still needs the owner's yes (publish, writes).

Done when: the owner can read the summary without opening anything else, and every claim in it points to a logged run.
