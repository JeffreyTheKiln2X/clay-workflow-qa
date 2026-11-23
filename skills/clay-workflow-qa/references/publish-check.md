# The publish check

Step f, part 5. Only when the owner says yes to publishing a fix.

The draft carries everything changed during the test, not only the fix: test switches turned off, edited
descriptions, leftovers. Publishing the draft publishes all of it. Publishing is never part of a fix.

## The check

1. Run `python3 skills/clay-workflow-qa/scripts/version_diff.py <wf>` (published version against the live
   draft). List every changed step and field in plain words for the owner. Exit code 1 means something differs.
2. Match each change to an approval. The owner's yes covers the changes they were shown. Anything else gets set
   back to the published value, or asked about: a write switch flipped for testing, a description that no longer
   matches the code.
3. Set every write switch to its published value unless the owner approved a change to it. Make each step's
   description match its code.
4. Rerun the diff. Publish only when every remaining difference is approved:
   `clay workflows publish <wf> --name "<what changed>"`. The version name says what changed.
5. After publishing, run `python3 skills/clay-workflow-qa/scripts/version_diff.py <wf> <old snap> <new snap>`
   and check the new version holds exactly the approved changes.

## After the publish

- A publish moves the manual trigger to the new version. Note which version each trigger now runs.
- The draft now equals production, with its write switches on. Turn test switches off again before any further
  draft run. Tell the owner.
- A play with a test copy: the copy does not move. Remake it (`test-copy.md`) before the next test of the new
  version.
- Add one dated line to the team's change log for the workflow (version, what changed, who approved).

## Notes on `version_diff.py`

- With no snapshots it checks every code step of the live draft against the newest snapshot. A snapshot is saved
  before each edit, so the newest edit may be in no snapshot yet.
- `nodes get` and `snapshots get` return steps in different shapes (`code` against `currentScriptVersion.code`).
  Compare snapshot to snapshot; the script handles this.
- Draft history and undo points: `clay workflows snapshots list <wf>`, `snapshots get <wf> <snap>`.

Pass: the new published version differs from the old one only by approved changes, and the owner knows the
draft's write switches are live again.
