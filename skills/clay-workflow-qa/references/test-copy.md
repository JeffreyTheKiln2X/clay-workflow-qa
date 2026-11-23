# The test copy

A live play with dry run off is never the target of steps c and d: a run there is a real run. Test a copy.

## What the copy is

`python3 skills/clay-workflow-qa/scripts/test_copy.py make <play> <workflow id> --tag <tag>`

The tag is a short word with no spaces that marks every part the test makes (for example the date and your
initials, `1119mp`).

| Part | Name | Why |
|---|---|---|
| The workflow | `TEST <tag> COPY: <live name>` | Every step of the live workflow, the same function calls by id, the same code |
| Dry run | The Settings step's switch set to `True` | Every write function decides and writes nothing outside Clay |
| Stand-in fields | `TEST <tag> <field name>`, one for each Audiences field a write step names | The copy writes the stand-ins. A run on a real record changes no live field, so no live segment moves |
| A trigger segment | `TEST <tag> COPY <live (t) name>` | The live `(t)` filter with the stand-ins swapped in, plus "name starts with TEST <tag>". Only a test record can start the copy, and a run moves it out |
| The trigger | On enter, on that segment | The same kind as the live one |

`make` stops when the live draft differs from the published version: a copy of the draft would test edits
that are not live. Ask the play's owner which to test; when the owner asked to test an unpublished rebuild, `--draft` copies the draft.

`make` never publishes. Step c runs the copy's draft (`runs test`), so it needs no publish.

**A signal workflow** (no trigger segment): a trigger with no segment gets a `manual` trigger on the copy, so step c
starts runs by hand with the record's fields. A scheduled trigger on `(r)` gets a copy of `(r)`.

**When stand-ins cannot be made** (People at Clay's 100 text field cap): `--echo-writes` turns each Audiences
write step into a code step of the same name and edges that returns `would_set <field>`; `--keep-write "<step>"`
keeps a step that must really write (the repeat guard's claim), with a stand-in for its fields; `--sub-code OLD
NEW` swaps text in every code step (a field the code reads by name, such as the claim field).

**Approvals.** `runs test`, `workflows delete`, `audiences archive` and `fields delete` wait in Clay's approval
queue. Pass `--approve` to `test_copy.py` or `smoke.py` only after the owner's yes for that run or delete.

## Read it back

`test_copy.py check <play>`: dry run on in the Settings step, every write step names a stand-in, the step
count equals the live workflow's. A FAIL stops the test.

## Publish it (step d only)

A trigger fires only on a published version. `test_copy.py publish <play>` checks the copy, publishes it and
reads the trigger back. A TEST copy with dry run on and no send is a test mode publish; it still waits for the
owner's yes in step d.

## What the copy cannot prove

- The live play's own version: the copy runs the same steps, not the same version id.
- A write to a live field: the copy writes stand-ins.
- Code that reads the record by field name reads the live field, not the stand-in. A test record must be made
  so the live field does not stop it (`trigger-test.md`, "Keep it out of the live play").

## Delete it

`test_copy.py delete <play>` deletes the triggers and the workflow, archives the trigger segment, and deletes
each stand-in field that no other segment reads (a field delete rewrites every segment that filters on it).
It reads each part back as gone.
