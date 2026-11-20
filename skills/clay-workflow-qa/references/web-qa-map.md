# Web QA practices, mapped to Clay workflows

| Web QA practice | In a Clay workflow | Skill step |
|---|---|---|
| Staging vs production | Draft vs published version. Test the draft with writes off | 1, 6 |
| Risk-based test plan | Rank by harm: writes > paid steps > decision logic > message text | 1, 5 |
| Requirements traceability | Each rule in the workflow points to a decision or owner. A rule with no source is a question for the owner | 3 |
| Smoke test | One known record, full run on the draft | 6b |
| Unit test | One step alone with made-up inputs (`nodes test --inputs`) | 6a |
| Equivalence partitioning | One record per outcome class; more of the same class adds cost, not coverage | 5, 6c |
| Branch / path coverage | List every end result; cover each one live or by a single-step test | 2, 5 |
| Boundary values | The edges of each rule: a date limit, a size limit, blank vs present | 5 |
| Negative testing | No record, blank fields, wrong region, duplicates | 5, 6a |
| Integration / contract testing | Inputs into called workflows wired, outputs read correctly, versions pinned, no hidden writes inside | 1, 3 |
| Regression testing | After a fix, replay the changed step on past runs and rerun the smoke | 6e |
| Exploratory testing | Cross-tab past run outputs for fields that should agree | 4 |
| Data integrity | Record fields before and after each run: 0 changed | 7 |
| Security / permissions | Every path that writes to Audiences, a CRM or messaging | 1 |
| Performance / cost | Credits and duration per run and per path | 2, 7 |
| Bug report | Severity, repro (run id), expected vs actual, cause, fix, retest | 8 |
| Test case management | A test log and one sheet row per run | 9 |
| QA sign-off | A short owner summary with coverage, bugs and open decisions | 9 |
