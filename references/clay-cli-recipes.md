# Clay CLI recipes for workflow QA

Run `clay <command> --help` for flags; output is JSON. If the workspace uses its own login folder, prefix every command with `CLAY_CONFIG_HOME=<folder>`. Check `clay whoami` names the right workspace before anything else.

## Read the workflow

| Need | Command |
|---|---|
| Name, published version | `clay workflows get <wf>` |
| All steps and edges | `clay workflows graph get <wf>`, `clay workflows diagram <wf>` |
| One step in full (code, inputs, rules) | `clay workflows nodes get <wf> <node>` |
| Structural problems | `clay workflows graph validate <wf>` |
| Triggers and the version each runs | `clay workflows triggers list --workflow-id <wf>` (`snapshotId: latest` = draft) |
| Downstream of a write: every live trigger in the workspace | `clay workflows triggers list --scope live` (`audience_segment` fires on segment membership change; `segmentId: ALL` watches every record; `paused` does not fire) |
| Downstream of a write: live triggers on one segment | `clay workflows triggers list --scope live --segment-id <segment>` (explicit assignments only; check `ALL` ones too) |
| A segment's filter (which fields it reads) | `clay audiences list --entity-type people`, then `clay audiences get <segment>` |
| Published versions | `clay workflows versions list <wf>` |
| Draft history, undo points | `clay workflows snapshots list <wf>`, `snapshots get <wf> <snap>` |
| What a publish would change, or did change | `scripts/version_diff.py <wf>` (published vs draft), `scripts/version_diff.py <wf> <old snap> <new snap>` |
| Publish (owner's yes only) | `clay workflows publish <wf> --name "<what changed>"` |
| A called workflow's steps | `clay workflows snapshots get <called wf> <its published snap>` |

## Read runs (0 credits)

| Need | Command |
|---|---|
| Runs, credits per run, filter by version | `clay workflows analysis runs --workflow <wf> --input '{"workflowSnapshotId":"<snap>","limit":100,"versionScope":"all"}'` (page with `nextCursor`) |
| Totals by version or day | `clay workflows analysis aggregate --workflow <wf> --input '{"groupBy":["snapshot_version"],"versionScope":"all"}'` |
| One run, which steps ran | `clay workflows runs get <run> --nodes` |
| One step's inputs and outputs in a run | `clay workflows runs get <run> --verbose --node-id <node>` |

## Run tests

| Test | Command | Runs |
|---|---|---|
| Full run on the draft | `clay workflows runs test <wf> --inputs '{"<trigger input>":"..."}'` | Draft. Check the returned `workflowSnapshot.id` is the draft, not the published id |
| Single step, made-up inputs | `clay workflows nodes test <wf> <node> --inputs '<json>'` | That step only; nothing after it |
| Single step, replay a past run | `clay workflows nodes test <wf> <node> --source-run <run>` | That step only, with the run's saved inputs |
| Wait for a result | `clay workflows runs get <run> --wait 300` | |

## Read and compare records

`clay audiences records get --entity-type people --ids <id,id>` (up to 100 ids). Field ids and names: `clay audiences fields list --entity-type people`. Segment filters: `clay audiences get <segment>`.

## Gotchas

- `runs test --live` runs the **published** version, with its writes. Leave `--live` off for QA.
- Some workspaces hold every CLI run for approval (beta, set by Clay per workspace): `runs test` and `nodes test` return `approval_required` with `details.actionApprovalRequestId`, one request per run, even at 0 credits. Get the user's yes for the test set, check each request's `details.input` (workflow, `startingNodeId`, inputs) matches the test, then `clay approvals approve <id>`; the run id is in `result.body.workflowRun.id`. Leave `--always-allow` off: its standing rule also lets writing runs through. Each blocked retry leaves a new pending request; deny the ones you will not run. The approval is not a write safety: it holds every run the same way, writing or not, so an approved run is only as safe as the switches set in step 1.
- A replay of a step you just edited reuses the old run's saved inputs, so a **new input arrives blank**. Pass it with `--inputs` on top of `--source-run`, using the value from the source run's upstream step.
- A step test of a code step costs 0 credits; a step test of a paid step costs what the step costs.
- A called workflow runs its latest published version unless the caller is pinned. The CLI cannot show or set a pin; check it in the app.
- Audiences cannot clear a value once written, and the CLI has no record edit. A wrong write stays until overwritten.
- The CLI cannot delete Audiences records either. Archive works on a whole segment in the app; permanent delete is Admin only (app delete in beta behind a flag, or the privacy-delete API, no undo). Deleting a segment removes only its filter; the records stay.
- An action credit can be charged on top of each data credit, and a called workflow can charge more action credits than data credits. Estimate both kinds.
- `nodes get` and `snapshots get` return steps in different shapes (`code` vs `currentScriptVersion.code`). Compare versions snapshot to snapshot; `version_diff.py` handles this.
- A snapshot is saved **before** each edit, so the newest edit may not be in any snapshot yet. `version_diff.py` with no snapshots checks the live draft against the newest one.
- A publish moves the manual trigger to the new version, and the draft now equals production with its writes on.
- Fallback paths (URL finders, AI verifiers, waterfalls) can cost several times a normal run. Run records likely to hit them one at a time near a stop line.
- A segment's filter may read a different column than the one the workflow writes. Compare field ids, not names.
