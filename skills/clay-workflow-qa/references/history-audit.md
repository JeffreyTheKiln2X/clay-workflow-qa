# The history audit

Step a, part 3. Free: 0 credits, reads only.

The doc says what should happen. Past runs show what did. Mine them before spending anything: where two fields
that should agree do not, a bug is hiding.

## 1. Pull the outputs

`python3 skills/clay-workflow-qa/scripts/run_audit.py <wf_id> <node_id> --fields status,reason_code,label --out runs.json [--snapshot <wfs_id>] [--crosstab status,label] [--workers 8]`

It lists every run of the workflow, reads the result step's outputs from each, saves them, and cross-tabs two
fields. Runs with no output for that step (the step did not run, or a single-step test of another step) are
skipped and counted. Set `CLAY_CONFIG_HOME` first on a workspace with its own login folder.

Pick `<node_id>` as the step that writes the final status or decision (`clay workflows graph get <wf>`).
Keep `runs.json` out of git: it can hold personal data. Delete it when the test is done.

## 2. Cross-tab fields that should agree

Run `--crosstab` on each pair:

- An early flag against the final status (a "guard hit" flag against a status that is not `out`).
- A label or score against the final decision.
- A reason code against the status it belongs to (each reason has one status).
- Anything the doc says moves together.

Each disagreement is a lead, not yet a bug: read the step, then file a finding with the run ids that show it.

## 3. Count the outcomes already seen

Write the possible end results, one per line, in a text file (the reason codes read from the decision step, or
the doc's status set). Then:

`python3 skills/clay-workflow-qa/scripts/outcome_coverage.py runs.json outcomes.txt --field reason_code [--extra tested.txt]`

It prints each outcome, how many runs showed it, and how it is covered: `live runs`, `other test` (from
`--extra`, one outcome per line, for outcomes proven by step tests), or `MISSING`. It also lists values seen but
not in your list: add them or check them.

The `MISSING` rows feed the plan checkpoint (the outcome matrix) and the picks for step c.

Pass: every key output field cross-tabbed against the final result; the outcome coverage so far known.
