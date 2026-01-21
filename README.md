# Claude Parallel Sessions

Run 4+ Claude Code sessions in parallel on the same codebase with clean, attributable commits.

Been using Claude Code daily for about 6 months now and this is the first thing I've felt the need to share.

## The Problem

I wanted to run multiple Claude sessions working on different backlog items at the same time while I focus on writing specs and managing the kanban. Tried git worktrees (need separate dev environments), GitButler (doesn't track which agent made which change), various Claude worktree managers (added complexity without solving my problem), separate branches (merge conflicts everywhere).

What I actually needed was simple:
- Run 4+ Claude sessions in parallel
- All sharing the same local dev environment
- Know exactly which files each agent touched
- Get clean commits

## The Solution

Claude Code has a hooks system. This repo contains a ~400 line Python script that fires after every Edit/Write/Read call. It logs which session touched which file to a JSON file in `.claude/sessions/`.

It also parses sub-agent transcripts. I use agentOS (from buildermethods) since it handles sub-agents well and is lighter weight than BMAD, but any spec-driven development framework would work fine with this. When Claude spawns sub-agents to implement a spec, those file edits get attributed back to the parent session.

## Day to Day

Open 4 terminal tabs. Each one runs `claude`. Give each session a different task from my backlog. They all work simultaneously, all hitting the same localhost frontend and backend.

I give the sub-agents instructions to check frontend and backend logs, clear TS errors, use common sense to figure out if an error is related to their work or not. It works well. If two agents are both doing frontend work and something breaks, they're decent at identifying who caused it and fixing their own mess.

When an agent finishes, I run `/wrapup` which:
1. Reads the session tracking data
2. Stages only that session's files
3. Reviews any .md files the session read during its work and updates them if needed
4. Creates a clean commit

You can pass in specific docs as arguments to force update them (like `/wrapup docs/PRD.md`).

All on main branch. All in the same worktree.

## Results

After a week of battle testing: I barely have to babysit the agents. Most of my time is spent drafting specs and managing the backlog. Not for production critical work but great for moving fast on a prototype without complex agent management systems.

## Setup

1. Copy `.claude/` folder and `scripts/` to your project
2. Add the multi-agent section from `examples/CLAUDE.md` to your project's CLAUDE.md
3. Add `.claude/sessions/` to your `.gitignore`

The hooks config uses relative paths so it should work as-is. If you need absolute paths (Windows sometimes), update `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|Read|Task",
        "hooks": [
          {
            "type": "command",
            "command": "python /full/path/to/scripts/track-file-change.py"
          }
        ]
      }
    ]
  }
}
```

## Files

```
.claude/
  settings.local.json    # Hook configuration
  commands/
    wrapup.md            # /wrapup command for clean commits
scripts/
  track-file-change.py   # PostToolUse hook - tracks file edits per session
  stage-my-files.py      # Stage helper for commits
examples/
  CLAUDE.md              # Example section to add to your CLAUDE.md
```

## Commands

```bash
# List all tracked sessions
python scripts/stage-my-files.py --list

# Show what a session touched
python scripts/stage-my-files.py --show abc123

# Stage only that session's files
python scripts/stage-my-files.py abc123

# From within Claude, wrap up and commit
/wrapup
/wrapup docs/PRD.md  # Force update specific docs
```

## Session JSON Structure

```json
{
  "session_id": "b9a65865-89b4-...",
  "started": "2025-01-20T17:49:49",
  "files": [
    {"path": "src/hooks/useDirtyDetection.ts", "action": "edit", "time": "..."},
    {"path": "src/api/client.ts", "action": "subagent", "agent_id": "xyz123"}
  ],
  "file_set": ["src/hooks/useDirtyDetection.ts", "src/api/client.ts"],
  "docs_read": [{"path": "docs/architecture.md", "time": "..."}],
  "docs_set": ["docs/architecture.md"]
}
```

## Customization

Edit `scripts/track-file-change.py` to configure which docs to track:

```python
TRACKABLE_DOC_PATHS = [
    "docs/",  # Track docs folder
]
EXCLUDED_DOC_PATTERNS = [
    "CLAUDE.md",      # Human-controlled
    "docs/specs/",    # If using spec-driven dev
]
```

## License

MIT
