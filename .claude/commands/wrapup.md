# Wrap Up Session

Finalize session: review docs for updates, stage files, commit.

**Usage:** `/wrapup [file1.md] [file2.md] ...`
- No args: update docs based on session read history
- With args: force-update specified files, then standard flow

## Flow

### 1. Load Session Data
Read `.claude/sessions/<session_id>.json` for `file_set` (edited) and `docs_set` (read).
Parse any arguments as `force_docs` (guaranteed updates).

### 2. Review Docs
1. **Force docs** (from args): Update regardless of heuristics
2. **Session docs**: Review docs the session read, update only if the session's changes made them stale

**Skip:** `**/CLAUDE.md` (human-controlled)

### 3. Stage & Commit
```bash
python scripts/stage-my-files.py <session_id>
git add <any newly edited docs>
git commit -m "<type>: <summary>"
```

## Example
```
/wrapup docs/PRD.md

1. Load session, force_docs=[docs/PRD.md]
2. FORCE update PRD.md with session context
3. Review other docs_set items (skip if no changes needed)
4. Stage all, commit: "feat: add user auth; update PRD"
```

## Important
- **DO NOT** restart services, run builds, or create new files
- **DO NOT** update CLAUDE.md (human-controlled)
- Keep doc updates minimal and focused on what changed
