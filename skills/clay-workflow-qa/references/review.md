# The review

Step f. Go through every check below on this play, and write one line for each finding: what you saw, its
proof (a file and line, a Clay id, a run id, a count) and one pick. A check with nothing to say gets no line.
Sources: the team's workflow method doc, if it has one, and its list of known Clay gotchas.

## First: the play's rulings

Before any check, list the play doc's **rulings**: each rule row with the owner's quote and a date (for
example "Time bound blocks end `out`", with the owner's name and date). A ruling outranks the method. A check that
a ruling answers is not a finding: write it once in the report under "Ruled, not flagged", with the ruling's
doc line, and go on. A check the ruling does not name is still a finding.

## Findings, most severe first

1. **What failed.** Every FAIL row of steps a to e, with the step and the run. Every FAIL row of the coverage
   table: the play does not do what its doc says.
2. **What the doc and the code do not share.** Each `NO TEST` row, each line of "Code with no doc rule" and
   each line of "Doc rule with no code" (`spec.md`). Pick the fix: a test, a doc line, or a code change.
3. **What can send a wrong email.** A write path the safety gate found that no switch covers, a switch listed
   **unverified** (`safety-gate.md`), a called workflow that writes or posts without reading the dry run switch, a
   live `ALL` trigger or segment chain downstream of a field the play writes. A guard that reads a copy of a
   fact instead of the system that owns it (a
   bounce read from the CRM instead of the sender; an open deal read from a Clay field). A live part with dry run off and
   no hold. A record a live trigger segment holds that the play doc says is out. A send switch that differs
   between the doc and the published code.
4. **What can lose a record.** A block that can pass with time (an open deal, a re-engage date, a recent sales
   touch) that ends in `out`, unless the play doc rules it `out`. Rule: it ends in `review`, and `out` is for a
   lasting reason only. A lost read
   that ends in `out`. A record that sits in `(t)` for more than a day with no run (the trigger missed it).
5. **What costs more than it needs.** A paid step before a free guard that would refuse the record. Credits per
   record above the doc's estimate.

## Improvements

| Check | What good looks like | How to see it |
|---|---|---|
| Segments (only when the target sets `convention: ior_t`) | `(i)`, `(r)`, `(o)`, and one `(t)` for a field play. The guard block appears once in each filter | `static_check.py --filters`: count the repeated guard clauses |
| Status | One status set: empty, `ready`, `review`, `out`, and the play's success word. A dry run writes no status of its own (`staged`, `DRY_RUN`) | The smoke results on the stand-in or TEST status |
| Holds | One hold field for every "wait" or "never"; no person or account typed into code | `grep` the play's code for ids and names in lists |
| Guards | Each guard reads the system that owns the fact: the CRM for the account and the deal, the sender for a bounce | The play's guard code and the Guards function |
| Columns | Each fact column has a reader. Fewer columns are better | The target's fields against the doc's column table |
| Credits | Credits per record, data and action apart, against the doc | The smoke and the trigger run |
| Names and delete dates | No live part keeps `TEST `; every retired part has a `delete_by` date | the target's `repo_checks`, or a read of the part names in Clay |
| Values | Every client value (a window, a cap, a list) lives in a config the client can edit, read at run time. One source per value | `grep` the play's code for numbers and lists not marked structural |
| Trigger health | No record in `(t)` for more than a day | a read of the trigger segment's count and its oldest member |

Write each improvement as: what to change, why (the rule or the finding), and the size (small, one thread,
needs a ruling).
