# Example CLAUDE.md Section for Multi-Agent Tracking

Add this section to your project's CLAUDE.md to enable multi-agent session tracking.

---

## Multi-Agent Session Tracking

Multiple Claude sessions may run in parallel. Each session's file modifications are auto-logged to `.claude/sessions/<session_id>.json`.

### Committing Your Work
1. **Check your session's files:** `python scripts/stage-my-files.py --show %CLAUDE_SESSION_ID%`
2. **Stage only YOUR files:** `python scripts/stage-my-files.py %CLAUDE_SESSION_ID%`
3. **Commit with session prefix:** `git commit -m "[session:abc123] feat: description"`

### Multi-Agent Debugging
- When debugging: first check if error relates to YOUR modified files
- If error is in a file you didn't touch, note it but don't fix unless asked
- Use `git diff <file>` to see changes before making assumptions

### Session Files
- `.claude/sessions/*.json` - Per-session tracking (gitignored)
- `scripts/stage-my-files.py` - Stage helper: `--list`, `--show <id>`, `<id>`
- `scripts/track-file-change.py` - PostToolUse hook (runs automatically)

---

## Optional: Sub-Agent Instructions

If you use spec-driven development with sub-agents (agentOS, BMAD, etc.), add instructions like:

### For Sub-Agents
- Check frontend logs (`logs/frontend.log`) and backend logs (`logs/backend.log`) for errors
- Clear TS errors before completing
- Use common sense: if an error is in a file you didn't touch, it's probably not your bug
- If two agents are working on frontend simultaneously, identify which agent's changes caused any issues
