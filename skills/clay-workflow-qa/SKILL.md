---
name: clay-workflow-qa
description: "QA a Clay workflow or play: prove it does what its doc says and nothing it should not. Safety gate, spec, history audit, edge cases, cheapest tests first, a test copy for live workflows, trigger test, canary, bug reports, publish check, and a plain-words results page. Use when someone asks to QA, test, audit, prove, dry run or check a Clay workflow (a play, a module, any wf_ id), to run a trigger test, to find bugs in one, or to review one before a handoff or a switch on."
---

# Clay workflow QA

Act as a **senior QA engineer** on a Clay workflow. The draft is your **staging**, the published version is **production**. You test on the draft or on a test copy, you change nothing in production, and every finding comes with evidence (a run id, a count, a before and after).

Two questions, both answered: does it do what its doc says (**spec**), and can it do anything the doc does not say, a write or a send nobody listed (**risk**). The doc is the spec: every expected result comes from the doc, never from the code.

Needs: the Clay CLI logged in to the right workspace (`clay whoami` shows it; if the team has a workspace guard, run it first) and read access to the workflow, its runs and Audiences. Python 3 for the scripts in `scripts/`.

**Targets.** A target is a workflow or a play (a group of workflows) that the scripts know by name. It is one entry in a targets file (`--targets <file>` or env `QA_TARGETS`, default `./qa/targets.yaml`): its `doc`, workflows, segments, triggers, status columns, and optional `repo_checks`, `convention`, `credit_limit`. With a bare `wf_` id and no entry, use the scripts that take a workflow id, and see "No doc" in `references/spec.md`. In this skill, "play" means a target.

Files in `references/` carry the detail for each step: [`spec.md`](references/spec.md), [`safety-gate.md`](references/safety-gate.md), [`history-audit.md`](references/history-audit.md), [`edge-cases.md`](references/edge-cases.md), [`test-copy.md`](references/test-copy.md), [`trigger-test.md`](references/trigger-test.md), [`review.md`](references/review.md), [`publish-check.md`](references/publish-check.md), [`bug-report.md`](references/bug-report.md), [`report.md`](references/report.md), [`results-page.md`](references/results-page.md), [`clay-cli-recipes.md`](references/clay-cli-recipes.md) (commands and gotchas), [`web-qa-map.md`](references/web-qa-map.md).

## Hard rules

- **The client's CRM and their people stay untouched, always.** Every run keeps CRM writes (Salesforce, HubSpot, any CRM) and outbound messages (Slack, email, campaign or sequence enrollment) off or in dry run, including runs where an Audiences write was approved. Off means the step does not send. Pointing it at a test channel, inbox or webhook still sends, so it counts as on: allowed only when the owner approved that target and no one from the client can see it. Check each one is off before every run and absent after it. Turning one on is outside QA: it needs the owner's yes and the client's yes, in writing.
- **A write needs a yes to that write.** "Test it" or "run it" is not a yes. Before any run, say in plain words what it would write, where, and that Audiences values cannot be cleared; then wait. One yes at the plan checkpoint covers every stand-in write of the plan, and nothing outside it.
- **Real records for writes, fake only where nothing else works.** Smoke and canary runs use records already seen in past runs, writing to stand-in or status fields. Fake records (`example.com`, named "TEST <tag>") are for the trigger test only, where the copy's segment admits only a name-gated test record. An Admin agrees to delete them before the trigger test starts: no CLI deletes a record.
- **Staging only.** Runs go on the draft or the test copy (`clay workflows runs test`, no `--live`). The app's Run button and a manual trigger run the **published** version.
- **Price before you run.** State the estimate in data and action credits apart, set a stop line (estimate plus 20 percent), report the actual after. Lead with the smallest test that answers the question (a code step test is 0 credits). Leave out paid steps the test does not need. The target's credit limit (default 20) is where you stop and ask.
- **Pass bars before results.** Write the expected outcome of each test before running it. A bar written after the result is a story. A FAIL stops the climb: report it, and go back only after the fix.
- **Change only what was approved.** A fix goes into the draft only, after a snapshot. Publishing is the owner's call.

| Step | What it proves | Costs | Stop for a yes |
|---|---|---|---|
| 0. Spec | Each rule of the doc has a test, with the result the doc expects | 0 | Yes, when the doc is thin |
| a. Static check | The parts match the doc; every write path is found and made safe; past runs agree with themselves | 0 | No |
| Plan checkpoint | Outcomes and edge cases listed, each with a bar; cost and writes stated | 0 | Yes: the plan |
| b. Step tests | Each code step gives the right answer, edges included | 0 | No |
| c. Dry run smoke | One real record per outcome class runs, and nothing is written outside the test | Credits | Over the credit limit |
| d. Trigger test | A test record starts the workflow by its real trigger and leaves its trigger segment | About 0 | Yes |
| e. Canary | One real record, real writes | Real cost | Yes, and a runbook |
| f. Review | Bugs, findings, fixes, improvements | 0 | Yes, per fix |

Steps d and e apply to a workflow with a trigger or a live play; skip them with a stated reason when they do not (an on-demand function has no trigger to test).

## Before step a

1. Check the workspace (`clay whoami`, and the team's guard if it has one). Any other workspace stops the session.
2. Read the target's doc and any list of Clay gotchas the team keeps.
3. Open the report: copy `references/report.md` to `<target folder>/tests/<date>-test-play.md`. Fill in every pass bar now. The run also ends in a results file and a page (`references/results-page.md`): keep each record's outputs and the trigger times as they come, since the page draws them.

## 0. Spec (free)

Follow `references/spec.md`: it checks the doc is thick enough (a thin doc stops the session: ask the owner), then lists every rule as a row of the report's coverage table with its doc line, its test and the result the doc expects. A rule whose right answer is a business choice the doc does not make is an **owner call**: test what it does now and report it as a question, not a bug.

Pass: every rule row has a test.

## Talk to the operator

The person who runs this skill must see what the workflow did, not only pass marks, and hear at once when something looks wrong.

- **After each step**, one chat line before the next step or the next ask for a yes: what ran, what it proved, what comes next.
- **An alert, the moment it shows**, in the chat and in the report's alert block: what looks wrong, the record that shows it, why it matters (it can send a wrong email, lose a record, or cost credits) and the fix. A FAIL row, a coverage row whose actual differs from the doc, a live field changed, an unlisted write path and a write outside the test are each an alert.
- **The report opens with the verdict**: `Ready to go live` (every step PASS or skipped with a reason, every rule proven, 0 open alerts, every record equal), `Fix first` or `Blocked`, then "N of M documented rules proven". The page draws the same verdict from the results file.
- **Real outputs.** For each smoke and trigger record, one line of what the workflow did (status and reason, people picked, the would-do lines, the message as it would post) beside what the doc expected. `smoke.py` saves these in `written` and `outputs`.

## What needs a yes

The owner says yes in words, for one step, by name. A yes for one step is never a yes for the next.

- The plan checkpoint (covers the plan's stand-in writes and its cost, as stated).
- Step c above the credit limit. Step d: the test copy's publish, the test record, the Admin's delete.
- Step e, every part of it.
- Any write outside Clay. Any message to a person. Any change to a live part. Any fix, any publish.

## Live or test: pick the target first

Step a prints the dry run switch of each workflow.

- **Dry run on, never published, or a TEST draft:** steps c and d run on the workflow itself.
- **Dry run off (the workflow is live):** steps c and d run on a **test copy**, never on the live workflow. Read `references/test-copy.md`, then make the copy.

A dry run switch is proven only when you read the code that uses it, in every write function and in every called workflow. A setting name or a description is a claim: list the switch as **unverified** and treat its step as live.

## a. Static check, safety gate and history audit (free)

1. `python3 skills/clay-workflow-qa/scripts/static_check.py <target> --filters`. It reads Clay: names, versions, draft against published, triggers, segments, status columns and the dry run switch, and runs the target's `repo_checks`. Compare each printed filter to the doc's segment rules.
2. **Safety gate.** Follow `references/safety-gate.md`: every way the workflow can write or send, inside every called workflow too, the switch behind each and its value in the draft and in the published version, and what sits downstream of every Audiences write (segments that filter on the field, live triggers on them, `ALL` triggers, what those send). Each path is listed with how it is made safe, or tested only up to the step before it.
3. **History audit.** Follow `references/history-audit.md`: pull the result step's outputs from every past run (`scripts/run_audit.py`), cross-tab fields that should agree, and count which end results past runs already showed (`scripts/outcome_coverage.py`). Disagreement is where bugs hide.

Pass: 0 FAIL rows, every filter matches the doc, every write path listed and made safe, every key output cross-tabbed. A WARN goes to the review (step f).

## Plan checkpoint (stop for a yes)

Write the plan in the report, then ask once:

- The **outcome matrix**: every end result (reason code or status), how past runs showed it, how this run will reach the rest. One record per outcome class, not many of the same.
- The **edge case set**: `references/edge-cases.md`, rule by rule and input by input, each with its expected result written first.
- The write list (stand-in fields, test records), the credit estimate (data and action apart), the stop line.

Pass: every outcome has a test or a stated reason it cannot be tested; the owner said yes.

## b. Step tests (free)

1. Run the target's unit tests, when it has them.
2. Run the target's Clay step test script when it has one: each code step in Clay, on the unit cases, must equal the local answer. Without one: `clay workflows nodes test <wf> <step> --inputs '{...}'`.
3. Run the edge cases of `references/edge-cases.md` that are code steps, with made-up inputs.

Code steps only: a write step or a function call tested alone still writes and still calls. A step that can write or send is tested only after its write is proven off. Inputs picked so the write branch "should not fire" are not a safety.

Pass: 0 unit failures; every Clay case equal; every edge case equals its bar or is filed as an owner call.

## c. Dry run smoke (credits)

1. Pick up to 5 real records from the trigger segment or from past runs, one per outcome class that past runs showed and one per class the plan still needs to reach: one that goes all the way, one held, one with a guard (an open deal, a customer), one with a blank input. Say why each. Run any record that may hit a fallback or a paid lookup alone when close to the stop line.
2. **Price it first** from past runs (`clay workflows runs get <run>`), data and action apart.
3. Run: `python3 skills/clay-workflow-qa/scripts/smoke.py <target> <id> ...` (add `--wf <id>` for a draft that is not a copy; `--sf-field`, `--sf-writer` and `--outreach` add the optional CRM and sequencing read backs when `sf` and a reader are set up).

**Verify every run**, five checks, logged per run: it completed with 0 failed steps; the write step did not run, or wrote only the approved stand-ins; nothing changed where the workflow can write (Audiences fields, table row counts and the touched rows, and HTTP calls, enrollments and started workflows absent from the step outputs); no CRM write and no message sent; no downstream workflow ran on the test records (read the runs of each workflow mapped in the safety gate); credits recorded. `smoke.py` reads the Clay fields and, when configured, the CRM and sequencing tool; check the other paths by hand from the run's step outputs. For a run you start by hand, use `scripts/record_diff.py`.

Pass: every run `completed`, every function call answered, 0 live fields changed, 0 CRM writes, 0 messages sent, 0 downstream runs. Count each error type apart. Read each record's result: is the status the one the doc predicts?

## d. Trigger test (stop for a yes)

Never on a live workflow with dry run off. Follow `references/trigger-test.md`: make a test record you control, check it is in no live trigger segment, move it into the trigger segment, wait in bounded checks up to 90 minutes, read back the run, the status and that it left the segment, then delete it and read back that it is gone.

Pass: one run, started by the trigger (`trigger` set on the run), within 90 minutes; the status written once; the record out of the trigger segment; 0 live trigger segments held the record at any check; the record and the helper gone.

## e. Canary (stop for a yes, from a runbook)

One real record, dry run off, from a written runbook: each step with its read back and its rollback, the old values saved first. Skip it when the workflow is already live and its first real records passed; say so in the report.

Pass: every read back equals what the step wrote, in every system, and again 15 minutes later (CRM sync).

## f. Review, bugs and fixes

1. Fill the coverage table's actual and pass columns from steps a to e.
2. Go through every check in `references/review.md`. Findings, most severe first: what failed, then what can send a wrong email or write wrongly, then what can lose a record, then what costs more than it needs. Then the improvements, each one line with its proof and one pick.
3. Write each bug as a finding with the fields of `references/bug-report.md`. Severity follows harm, not effort.
4. **A fix**, only with the owner's yes, only in the draft, snapshot first. Retest: replay the changed step on past runs (`clay workflows nodes test <wf> <step> --source-run <run>`; a new input arrives blank, pass it with `--inputs`) and rerun the smoke.
5. **A publish**, only on the owner's yes: `references/publish-check.md` (the draft carries every change made during the test, not only the fix).

## Close

1. Finish the report: the verdict and the alert block first, then the coverage table, one PASS or FAIL line per step, the credits spent (data and action apart), the findings and the improvements, and the owner summary: what was tested, coverage (outcomes seen of total, edge cases passed of total), bugs and their state, every owner call, and what still needs the owner's yes.
2. Clean up what the test made: `scripts/test_copy.py delete <target>`, the trigger test records (`references/trigger-test.md`, "Clean up"), and read each back as gone.
3. Add a dated line to the team's change log: the result and the report path.
4. **The page.** Read `references/results-page.md`. Write the results file next to the report, then draw it: `python3 skills/clay-workflow-qa/scripts/render_page.py <results file> --fragment <scratchpad>/<stem>.html`. A gap stops the script with the list: fill or reword each one and draw again. Then publish the page as a private Artifact when the Artifact tool exists, or open the local page, and give the link in the closing reply beside the verdict line the script printed.

Done means: every step has its PASS, FAIL or a reason it was skipped; the cleanup read back clean; the page drew with no gaps and its link is in the reply; the report, the results file, the page and the log line are saved.
