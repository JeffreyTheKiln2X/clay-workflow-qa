# The trigger test

Step d. It proves the one thing no other step proves: a record that joins the trigger segment starts the play
by itself, the run writes a status, and the record leaves the segment. Free, except the run itself.

Facts about Clay that shape it (Clay's trigger behavior):

- An on enter trigger fires on Clay's re-check of the segment: 10 to 80 minutes late. Wait up to 90.
- It never fires for a record already inside when it is switched on, and it never retries a failed start.
- A trigger on a workflow that was never published never fires, and nothing warns you.
- `clay workflows runs list` shows `trigger` only on a run a trigger started. That is the proof.
- No CLI deletes an Audiences record: delete in the Clay app.

## 1. The target

The play itself only when it is a TEST draft or in dry run. A live play: the test copy (`test-copy.md`), published
with `test_copy.py publish <play>` after the owner's yes.

## 2. The test record

Write a spec: `<target folder>/tests/trigger-record.json`. Format: the `scripts/trigger_test.py` docstring.

- **Records you control.** People at `example.com` (a reserved domain) or your own email. Never a real person.
  Fake CRM contact ids. A real CRM account id only when it is a test account with no deals.
- **Every input the play needs.** Read the trigger segment's filter (`static_check.py --filters`) and set each
  field it requires.
- **Keep it out of the live play.** The live trigger segment must refuse the record while the copy's segment
  admits it. The two filters differ only in the stand-in fields, so set one live stand-in field that the live
  filter refuses (for example a "last run at" field set to today when the live filter wants it empty or old). Then check that the play
  code does not refuse it too: code reads fields by name, so it reads the live value. `where` is the proof.

## 3. The run, with a bar before each check

```
S=skills/clay-workflow-qa/scripts/trigger_test.py
python3 $S make <play> <spec>      # bar: the record and its people made; in 0 live trigger segments; copy (t) 0
python3 $S enter <play>            # bar: in 0 live trigger segments; copy (t) holds 1
python3 $S watch <play> 10         # repeat, one bounded wait at a time, until FIRED or 90 minutes
python3 $S readback <play>         # bar: one run, by_trigger true, completed; status written; copy (t) 0
```

`make` names the record `PENDING <tag> ...`; `enter` renames it `TEST <tag> ...`, which is the entry. Each
`watch` waits at most 10 minutes. Between waits, do other work; never leave a background poller running.

No run after 90 minutes: the trigger failed. Read the trigger (`clay workflows triggers get <id>`: its
`snapshotId` is the published version), the segment count, and the record's fields. Write the result as FAIL.

## 4. Clean up

1. In the Clay app, delete the people first, then the record: open
   `app.clay.com/workspaces/<workspace>/people/<id>` (or `/companies/<id>`), "...", Delete record, Delete
   permanently. The ids are in `<play folder>/tests/<date>-state.json`.
2. `python3 $S gone <play>`: reads them back (bar: 0 left) and deletes the helper workflow.
3. `python3 skills/clay-workflow-qa/scripts/test_copy.py delete <play>`.
