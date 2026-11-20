---
type: llm
focus: trace
weight: 1
---

safety_gate.md traces step 7's write to f_x81 (priority_band) into seg_PRIORITY, whose live trigger runs wf_TESTSYNC05, a Salesforce upsert with no dry run, so sf_dry_run=True does not prevent a Salesforce write
