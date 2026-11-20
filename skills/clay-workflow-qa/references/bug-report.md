# Bug report template

One per bug, in the test log and the owner summary.

```
Bug: <one line, plain words>
Severity: critical (wrong write or data loss) | high (wrong result a user sees) | medium (wrong label, no harm yet) | low (wording, docs)
Where: <workflow id>, step <name and id>
What happens: <observed behaviour, with counts>
Expected: <what should happen, and the rule or owner it comes from>
Evidence: <run ids, counts, before/after diff>
Cause: <why, from reading the step>
Fix: <proposed change; draft only; needs whose yes>
Retest: <single-step tests, replays, smoke, and their results>
Status: open | fixed in draft | published | won't fix
```

Severity follows harm, not effort: a bug that would cause a wrong CRM write once a switch is on is high or critical even while the switch is off.
