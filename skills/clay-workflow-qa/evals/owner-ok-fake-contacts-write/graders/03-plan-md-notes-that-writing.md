---
type: llm
focus: trace
weight: 1
---

plan.md names the live ALL trigger (trg_D4, wf_TESTSCORE06 or #exec-pipeline) as firing on a write to any field, so writing to a test field such as qa_test_status does not avoid it; a general warning about downstream triggers without naming this one does not count
