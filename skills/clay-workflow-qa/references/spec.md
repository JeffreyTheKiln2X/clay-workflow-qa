# The spec: the doc, rule by rule

Step 0. The target's doc is the **spec**. The test proves the workflow does what the doc says, so every expected
result comes from the doc, never from the code. A result read from the code tests the code against itself.

## 1. Is there a spec?

Open the target's doc (`doc` in the targets file, `--targets`) and any design doc it points to for the live
part. The spec is thick enough when it states each of these in words:

| Part of the spec | What it holds |
|---|---|
| Rule table | Each rule (the audience, the windows, the exclusions, the skips), with its source |
| Status set | Each status with its entry rule and its exit rule |
| Segments | What each segment the workflow reads or writes holds, in words |
| Guards and holds | Each guard, each hold value and what it does to the record |
| Owner | Who gets the record, and what happens when there is no one |
| Switches | Each switch, its value now and its effect |

A part with no words is a **thin** spec. Stop before step a and ask the owner for it, naming the missing parts in
one line each. There is nothing to test against until they exist.

## 1b. No doc (a `wf_` id with no entry in the targets file)

A workflow with no target entry has no doc. Do not stop and do not test the code
against itself. Look for the rules in this order, and cite each source on its row:

1. A design doc, build record or module README the team keeps for this workflow.
2. A ruling or a decisions file: a rulings log, a config the client edits (target titles, thresholds, lists).
3. The workflow's own step descriptions, read as the builder's claim, not as proof.

A rule found only in step 3, or in no source, is an **owner call**: test what the workflow does now and report it
as a question for the owner, never as a bug or a pass. Name the rules the owner must rule on, one line each.
The review (`review.md`) still runs; its checks that need a doc (rulings, holds) are skipped with a reason.

## 2. List the rules

Write one row for each rule of the spec in the report's coverage table. One row is one testable claim:
"an open deal ends `out`", not "the guards". Cite the doc file and line where the rule is stated.

When two docs disagree on a rule, the newer ruling wins, and the older line is a finding (a stale doc row).
A rule ruled by the owner against the method (a quote and a date in the doc) is a **ruled** choice: its row
expects what the ruling says, and the review lists it under "Ruled, not flagged".

## 3. Give each rule a test

Each row gets at least one test, picked in this order (the cheapest that proves it):

1. A filter clause of step a (`static_check.py --filters`): segment rules.
2. A unit case of step b, by its printed name: decisions in code.
3. A Clay step case of step b: the same decision, run in Clay.
4. A smoke record of step c: a rule that needs real data (a CRM field, a function answer).
5. The trigger test of step d: the trigger and the status write.

Write the expected result from the doc before you read the actual. A rule with no test is a `NO TEST` row.

## 4. Read the code for logic the doc does not state

Read the play's code steps and the segment filters once, and list each branch, refusal word or clause that no
rule row covers ("a weak title is not picked"). These go in the list "Code with no doc rule". A rule row with
no branch in the code goes in "Doc rule with no code". Both lists are findings in step f.

## Pass

Every rule row has a test, and every test equals what the doc expects. A `NO TEST` row, a FAIL row and each
line of the two lists is a finding in step f.
