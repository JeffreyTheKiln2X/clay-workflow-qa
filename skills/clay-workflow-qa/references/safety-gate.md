# The safety gate

Step a, part 2. Free: reads only.

Find every way the workflow can write or send, decide how each is made safe, and get the plan's yes (the plan
checkpoint in `SKILL.md`) before any run.

## 1. List every write path

Check each of these, in the workflow and inside **every called workflow** (read each called workflow's
published version, not only the caller):

- Audiences update or upsert steps
- Clay table row adds or updates
- Salesforce, HubSpot or any other CRM step
- Slack or email steps
- HTTP or webhook calls to outside tools (n8n, Instantly, any API)
- Campaign or sequence enrollment
- Steps that start another workflow

Treat any step that is not clearly read-only as a write until its code or config proves otherwise. A generic
step (a "call API" step, a router) can hide a write behind its inputs: read what it is called with.

## 2. Find each write switch

For every write path, find the switch that turns it off (a code setting, `write_mode`, `dry_run`,
`slack_test_mode`) and its value in the draft and in the published version.

A switch is proven only when you read the step's code or config that uses it. A setting name, a description or
a comment saying so is a claim: list that switch as **unverified** and treat its step as live. A switch that
turns off one path does not cover a second path in the same step (a step that honors `slack_test_mode` for one
post and posts to the live channel in another branch).

On a live play the test copy flips only the copy's own Settings step (`test-copy.md`). Read each write function and
each called workflow for the switch too: a called workflow that does not read the copy's switch still writes.

## 3. Map what is downstream of every Audiences write

A write can set off another live workflow that sends for you. For each field and record the test could write:

1. Which segments filter on it (compare field ids, not names).
2. Which live triggers watch those segments: segment triggers, and `ALL` assignments that watch every record.
3. What those workflows do: campaign enrollment, CRM sync, messages.

Note which version each trigger runs (`snapshotId: latest` is the draft), and which are paused (a paused chain
does not fire). Note the guards that decide which records reach the writes: a guard that lets blanks through
widens every write.

Fake or test data does not make a write safe: the downstream workflow cannot tell the record is fake. Clay's
own bookkeeping (`updated_at`) changes on every run that touches a record, so an `ALL` trigger on record change
can fire even when no live field moved.

## 4. Pick how each path is made safe

Best first:

1. Write only to fields no live segment reads (the test copy's stand-in fields, `test-copy.md`).
2. Make the test records fail the segment filters, checked against the real filter.
3. Pause the downstream trigger or campaign, with the owner's yes and a named person who turns it back on.
4. Skip the write and test only up to the step before it (step b single-step tests).

If a write cannot be made safe, test only with single-step tests up to the step before it.

## 5. Write it in the report

One row per write path:

| Path | Where (workflow, step) | Switch | Draft value | Published value | Proven by | Made safe by |
|---|---|---|---|---|---|---|

Then one row per downstream chain: field, segment, trigger and its version, what it sends, live or paused.

Pass: every write path is listed with how it is made safe (switch off in the draft, dry run, or a step test that
stops before it); every switch is proven or listed **unverified**; every downstream chain is mapped; the owner
said yes to the plan.
