# Bug report template

One per bug, in the report's "Findings" and in the owner summary.

```
Bug: <one line, plain words>
Severity: high (wrong write, wrong send or lost record, even while a switch is off) | medium (wrong label, no harm yet) | low (wording, docs)
Where: <workflow id>, step <name and id>
What happens: <observed behaviour, with counts>
Expected: <what should happen, and the doc line or owner it comes from>
Evidence: <run ids, counts, before/after diff>
Cause: <why, from reading the step>
Fix: <proposed change; draft only; needs whose yes>
Retest: <single-step tests, replays, smoke, and their results>
Status: open | fixed in draft | published | won't fix
```

Severity follows harm, not effort: a bug that would cause a wrong CRM write once a switch is on is `high` even
while the switch is off. The results page has three levels, so a wrong write or data loss is `high`.
