# The edge case set

Part of the plan checkpoint; most cases run in step b.

Outcome coverage alone misses these: every outcome can pass while the edges of a rule are wrong. Go rule by rule
(the coverage table's rows) and input by input, and list each case with its expected result **written first**.

## The cases

- **Thresholds** (month limits, scores, counts, windows): test exactly at the line, one below and one above.
  Also test what happens when the setting itself is blank.
- **Inputs each step reads** (dates, ids, URLs, domains, names): test blank, junk, the wrong format, and an
  impossible value (a future date, a negative number).
- **Guards and filters** (region, status, already-done checks): test the blank value. A blank that passes a
  guard is the most common hidden gap, and it widens every write behind it. Also test one value that should
  fail.
- **Lookups** (record id, segment, called workflow): test no match, a bad id, and more than one match.
- **Fallbacks** (route defaults, "unknown" labels, refusal words): test the case that triggers each one.
  Refusal is the majority case on a real account list, so each refusal state (`NO_EVENTS_PAGE` and the rest) gets
  a case. An empty string is the answer for "not published", never null and never `0`.
- **Re-runs**: run the same record twice (duplicates, double sends), and a record whose result changes between
  runs (a fit record that becomes not fit: do the old values stay?).

## Decide what should happen

For each case, decide the expected result from the doc before you write the pass bar. If the doc is silent and
the right behavior is a business choice (should a blank location count as U.S.?), mark the case **owner call**:
test what it does now, and report it as a question in the owner summary, not as a bug.

## Where they run

Most cases run as single-step tests with made-up inputs (step b): 0 credits for code steps.

```
clay workflows nodes test <wf> <step> --inputs '{"<input>": "<value>"}'
```

A step test runs the step for real: only a step whose write is proven off (`safety-gate.md`) is tested this way.
Re-runs, and cases that need the whole path (a fallback inside a paid lookup), go to step c, one record at a
time near the stop line.

## Write them down

One row per case in the report, under the rule it belongs to:

| Rule # | Case | Input | Expected (from the doc, or owner call) | Ran in | Actual | Pass |
|---|---|---|---|---|---|---|

Pass: every threshold, input, guard, lookup and fallback in the play has its cases listed, and each case equals
its bar or is filed as an owner call.
