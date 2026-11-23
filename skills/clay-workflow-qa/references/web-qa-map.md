# Web QA practices, mapped to Clay workflows

Step ids are the ones in `SKILL.md`: 0, a, plan (the plan checkpoint), b, c, d, e, f, close.

| Web QA practice | In a Clay workflow | Step |
|---|---|---|
| Staging vs production | Draft vs published version. Test the draft, or a copy, with writes off | a, c |
| Risk-based test plan | Rank by harm: writes > paid steps > decision logic > message text | a, plan |
| Requirements traceability | Each rule points to a doc line, a decision or an owner. A rule with no source is an owner call | 0 |
| Spec-based testing | The doc is the source of every expected result, never the code | 0 |
| Smoke test | Real records, full run on the draft or the copy | c |
| Unit test | One step alone with made-up inputs (`nodes test --inputs`) | b |
| Equivalence partitioning | One record per outcome class; more of the same class adds cost, not coverage | plan, c |
| Branch / path coverage | List every end result; cover each one live or by a single-step test | a, plan |
| Boundary values | The edges of each rule: a date limit, a size limit, blank vs present | plan, b |
| Negative testing | No record, blank fields, wrong region, duplicates | plan, b |
| Integration / contract testing | Inputs into called workflows wired, outputs read correctly, versions pinned, no hidden writes inside | a |
| Test environment | A copy of the live workflow with stand-in fields, so a run on real records changes no live field | c |
| End-to-end / trigger testing | A test record starts the workflow by its real trigger and leaves the trigger segment | d |
| Canary release | One real record, real writes, from a runbook with a read back and a rollback | e |
| Regression testing | After a fix, replay the changed step on past runs and rerun the smoke | f |
| Exploratory testing | Cross-tab past run outputs for fields that should agree | a |
| Data integrity | Record fields before and after each run: 0 live fields changed | c |
| Security / permissions | Every path that writes to Audiences, a CRM or messaging, and what sits downstream | a |
| Performance / cost | Credits and duration per run and per path, data and action apart | plan, c |
| Code review / heuristics | A checklist of what can send wrong, lose a record, or cost more than needed | f |
| Bug report | Severity, repro (run id), expected vs actual, cause, fix, retest | f |
| Release check | Diff the draft against the published version before any publish | f |
| Test report | A markdown report plus a plain-words page: verdict, what each test account did, a fix list | close |
| QA sign-off | A short owner summary with coverage, bugs and open decisions | close |
