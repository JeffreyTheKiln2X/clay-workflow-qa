# Test report: <Play name>, <date>

Who ran it: <name>. Target: <the play itself, or the test copy and its id>. Tag: <tag>.
Spec: <the play doc and the design doc, with the commit read>.

## Verdict

**<Ready to go live | Fix first | Blocked>.** <N> of <M> documented rules proven. <One sentence: what the play did on the
test records and what stands before go live, in words the owner's team follows (no segment, trigger, node, status
column or dry run). The same sentence is `verdict.why` on the page (`results-page.md`).>

## Alerts

<None, or one block per alert:>

> **<What looks wrong.>** Record: <name and id>. Why it matters: <it can send a wrong email | lose a record |
> cost credits>. Fix: <the change, and who makes it>.

## Coverage (step 0: the doc is the spec)

<n> rules, <n> with a test, <n> PASS, <n> FAIL, <n> NO TEST.

| # | Rule (from the doc) | Doc line | Test | Expected (from the doc) | Actual | Pass |
|---|---|---|---|---|---|---|

**Code with no doc rule** (findings)

1.

**Doc rule with no code** (findings)

1.

**Ruled, not flagged** (a ruling in the doc answers the method check)

1.

## Safety gate (step a: `safety-gate.md`)

| Path | Where (workflow, step) | Switch | Draft value | Published value | Proven by | Made safe by |
|---|---|---|---|---|---|---|

Downstream chains (field, segment, trigger and its version, what it sends, live or paused):

1.

## Outcomes and edge cases (plan checkpoint: `history-audit.md`, `edge-cases.md`)

Outcomes: <n> possible, <n> seen in past runs, <n> reached by a test, <n> MISSING.

| Outcome | Seen in past runs | Reached by | Result |
|---|---|---|---|

| Rule # | Edge case | Input | Expected (doc, or owner call) | Ran in | Actual | Pass |
|---|---|---|---|---|---|---|

## Result

| Step | Pass bar (written before the run) | Result | Proof | Credits (data, action) |
|---|---|---|---|---|
| 0. Spec | Every rule row has a test | | | 0 |
| a. Static check, safety gate, history audit | 0 FAIL rows; every filter matches the doc; every write path listed and made safe (`safety-gate.md`); every key output cross-tabbed (`history-audit.md`) | | | 0 |
| Plan checkpoint | Every outcome has a test or a reason; edge cases listed with bars (`edge-cases.md`); the owner said yes | | | 0 |
| b. Step tests | 0 unit failures; every Clay case equal | | | 0 |
| c. Dry run smoke | Every run completed, 0 failed steps, every call answered, 0 live fields changed, 0 CRM writes, 0 messages sent | | | |
| d. Trigger test | One run by the trigger within 90 minutes; status written once; out of the trigger segment; 0 live trigger segments held the record; records gone | | | |
| e. Canary | Every read back equals the write, again after 15 minutes | | | |
| f. Review | Every check in review.md gone through | | | 0 |

## What the play did (smoke and trigger records)

| Record | Why picked | What the play did (status, reason, people, would-do lines, Slack text, CRM and sequencing tool read back) | What the doc expects | Equal |
|---|---|---|---|---|

## Findings, most severe first

1.

A bug, or a finding that is a defect, carries the fields of `bug-report.md`.

## Owner summary

What was tested; coverage (outcomes seen of total, edge cases passed of total); bugs and their state; every
**owner call** as a question; credits (data and action apart); what still needs the owner's yes (a fix, a
publish, a write).

## Improvements

1.

## Cleanup

| Part | Id | Read back |
|---|---|---|
