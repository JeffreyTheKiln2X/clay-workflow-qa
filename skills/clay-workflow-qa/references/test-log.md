# Test log template

A test log is one file per workflow, newest test first. Records go by record id only, never names, emails or phones.

```
# QA test log: <workflow name> (<wf id>)

## Setup
- Workspace, draft snapshot, published version, write switches and their values
- How to test without writing (exact command)
- Undo point for any draft change

## Tests

### T<n>. <what> (<date>)
Pass bars (written before the run): ...
Estimate: <data> data, <action> action; stop at <n>.
Result: PASS | FAIL | PASS with notes
| Record | Run | Got | Credits |
- Safety checks: failed steps, write step ran, fields changed, CRM write, message sent
- Findings and open questions
```

## Sheet columns (one row per run)

Test, Date, Run ID, Record ID, Version, What was tested, Expected, Result, Reason code, Data credits, Action credits, Write step ran, Record fields changed, CRM write, Message sent, Pass, Notes.
