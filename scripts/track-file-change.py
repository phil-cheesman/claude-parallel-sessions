#!/usr/bin/env python3
"""
PostToolUse hook: Track file modifications and doc reads per Claude session.
Logs to .claude/sessions/<session_id>.json

Hook input (stdin JSON):
{
  "session_id": "abc123...",
  "tool_name": "Edit",
  "tool_input": {"file_path": "...", ...},
  "tool_response": "...",
  ...
}

Tracks:
- Edit/Write/NotebookEdit -> files, file_set (for staging)
- Read on .md files -> docs_read, docs_set (for /wrapup review)
- Task completion -> parses sub-agent transcript for file changes
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Project root (where .claude/ lives) - determined from script location
PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / ".claude" / "sessions"

# Claude data directory (platform-specific)
if sys.platform == "win32":
    CLAUDE_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / ".." / ".claude"
    if not CLAUDE_DATA_DIR.exists():
        CLAUDE_DATA_DIR = Path.home() / ".claude"
else:
    CLAUDE_DATA_DIR = Path.home() / ".claude"

# Configure which docs to track for /wrapup review
# Customize these for your project
TRACKABLE_DOC_PATHS = [
    "docs/",  # Track docs folder
]
EXCLUDED_DOC_PATTERNS = [
    "CLAUDE.md",      # Usually human-controlled
    "docs/specs/",    # If using spec-driven dev, specs are handled separately
]


def ensure_sessions_dir():
    """Create sessions directory if it doesn't exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    # Add to .gitignore if not already there
    gitignore = PROJECT_ROOT / ".gitignore"
    ignore_line = ".claude/sessions/"
    if gitignore.exists():
        content = gitignore.read_text()
        if ignore_line not in content:
            with open(gitignore, "a") as f:
                f.write(f"\n# Claude session tracking\n{ignore_line}\n")


def get_session_file(session_id: str) -> Path:
    """Get path to session's tracking file."""
    # Use first 12 chars of session ID for filename
    short_id = session_id[:12] if len(session_id) > 12 else session_id
    return SESSIONS_DIR / f"{short_id}.json"


def load_session(session_file: Path) -> dict:
    """Load existing session data or create new."""
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text())
            # Ensure new fields exist for older session files
            if "docs_read" not in data:
                data["docs_read"] = []
            if "docs_set" not in data:
                data["docs_set"] = []
            return data
        except json.JSONDecodeError:
            pass
    return {
        "session_id": "",
        "started": datetime.now().isoformat(),
        "files": [],
        "file_set": [],  # Deduplicated edits
        "docs_read": [],  # Doc read entries with timestamps
        "docs_set": []  # Deduplicated doc paths
    }


def is_trackable_doc(file_path: str) -> bool:
    """Check if a .md file should be tracked for /wrapup review."""
    if not file_path.endswith(".md"):
        return False

    # Normalize path separators
    normalized = file_path.replace("\\", "/")

    # Check exclusions first
    for pattern in EXCLUDED_DOC_PATTERNS:
        if pattern in normalized:
            return False

    # Check if in trackable paths
    for path in TRACKABLE_DOC_PATHS:
        if normalized.startswith(path):
            return True

    return False


def save_session(session_file: Path, data: dict):
    """Save session data."""
    session_file.write_text(json.dumps(data, indent=2))


def extract_file_path(tool_name: str, tool_input: dict) -> str | None:
    """Extract file path from tool input based on tool type."""
    if tool_name in ("Edit", "Write", "Read"):
        return tool_input.get("file_path")
    elif tool_name == "NotebookEdit":
        return tool_input.get("notebook_path")
    return None


def get_project_dir_name() -> str:
    """Get the Claude project directory name.

    Converts project path to Claude's naming convention:
    C:\\dev\\my-project -> C--dev-my-project
    /home/user/project -> -home-user-project
    """
    project_path = str(PROJECT_ROOT.resolve())
    # Replace path separators and colons with dashes
    return project_path.replace(":\\", "--").replace("\\", "-").replace("/", "-")


def find_subagent_transcript(session_id: str, agent_id: str) -> Path | None:
    """Find the sub-agent transcript file."""
    project_dir = get_project_dir_name()
    transcript_path = CLAUDE_DATA_DIR / "projects" / project_dir / session_id / "subagents" / f"agent-{agent_id}.jsonl"

    if transcript_path.exists():
        return transcript_path
    return None


def parse_subagent_transcript(transcript_path: Path) -> list[str]:
    """Parse a sub-agent transcript JSONL for file modifications.

    Returns list of file paths that were edited/written by the sub-agent.
    """
    files_modified = []

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Look for assistant messages with tool_use content
                message = entry.get("message", {})
                if message.get("role") != "assistant":
                    continue

                content = message.get("content", [])
                if not isinstance(content, list):
                    continue

                for item in content:
                    if item.get("type") != "tool_use":
                        continue

                    tool_name = item.get("name", "")
                    if tool_name not in ("Edit", "Write", "NotebookEdit"):
                        continue

                    tool_input = item.get("input", {})
                    file_path = None

                    if tool_name in ("Edit", "Write"):
                        file_path = tool_input.get("file_path")
                    elif tool_name == "NotebookEdit":
                        file_path = tool_input.get("notebook_path")

                    if file_path:
                        # Normalize path
                        try:
                            fp = Path(file_path)
                            if fp.is_absolute():
                                file_path = str(fp.relative_to(PROJECT_ROOT))
                        except ValueError:
                            pass

                        file_path = file_path.replace("\\", "/")
                        if file_path not in files_modified:
                            files_modified.append(file_path)

    except Exception:
        pass

    return files_modified


def handle_task_completion(hook_input: dict, session_data: dict) -> bool:
    """Handle Task tool completion - extract files from sub-agent transcript.

    Returns True if any files were added.
    """
    import re

    # tool_response contains the Task result with agentId
    tool_response = hook_input.get("tool_response", "")

    # tool_response might be a string or dict
    if isinstance(tool_response, str):
        # Try to find agentId in the string
        match = re.search(r'"agentId"\s*:\s*"([^"]+)"', tool_response)
        if match:
            agent_id = match.group(1)
        else:
            return False
    elif isinstance(tool_response, dict):
        agent_id = tool_response.get("agentId")
        if not agent_id:
            agent_id = tool_response.get("toolUseResult", {}).get("agentId")
    else:
        return False

    if not agent_id:
        return False

    session_id = hook_input.get("session_id", "")
    if not session_id:
        return False

    # Find and parse the sub-agent transcript
    transcript_path = find_subagent_transcript(session_id, agent_id)
    if not transcript_path:
        return False

    files_modified = parse_subagent_transcript(transcript_path)

    # Add files to session data
    added_any = False
    for file_path in files_modified:
        if file_path not in session_data["file_set"]:
            session_data["file_set"].append(file_path)
            session_data["files"].append({
                "path": file_path,
                "action": "subagent",
                "agent_id": agent_id,
                "time": datetime.now().isoformat()
            })
            added_any = True

    return added_any


def main():
    try:
        stdin_data = sys.stdin.read().strip()
        if not stdin_data:
            sys.exit(0)

        hook_input = json.loads(stdin_data)

        # Get session ID
        session_id = hook_input.get("session_id", "")
        if not session_id:
            sys.exit(0)

        # Get tool info
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})

        # Track file-modifying tools, Read on .md files, OR Task completion
        is_edit = tool_name in ("Edit", "Write", "NotebookEdit")
        is_read = tool_name == "Read"
        is_task = tool_name == "Task"

        if not is_edit and not is_read and not is_task:
            sys.exit(0)

        # Ensure sessions directory exists
        ensure_sessions_dir()

        # Load/create session file
        session_file = get_session_file(session_id)
        session_data = load_session(session_file)
        session_data["session_id"] = session_id

        # Handle Task completion - parse sub-agent transcript for file changes
        if is_task:
            if handle_task_completion(hook_input, session_data):
                save_session(session_file, session_data)
            sys.exit(0)

        # Extract file path for Edit/Write/Read
        file_path = extract_file_path(tool_name, tool_input)
        if not file_path:
            sys.exit(0)

        # Make path relative to project root if absolute
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.is_absolute():
                file_path = str(file_path_obj.relative_to(PROJECT_ROOT))
        except ValueError:
            # Path not relative to project, keep as-is
            pass

        # Normalize path separators for consistency
        file_path = file_path.replace("\\", "/")

        # For Read: only track if it's a trackable doc
        if is_read and not is_trackable_doc(file_path):
            sys.exit(0)

        if is_edit:
            # Track file edits
            entry = {
                "path": file_path,
                "action": tool_name.lower(),
                "time": datetime.now().isoformat()
            }
            session_data["files"].append(entry)

            # Update deduplicated file set
            if file_path not in session_data["file_set"]:
                session_data["file_set"].append(file_path)

        elif is_read:
            # Track doc reads
            entry = {
                "path": file_path,
                "time": datetime.now().isoformat()
            }
            session_data["docs_read"].append(entry)

            # Update deduplicated docs set
            if file_path not in session_data["docs_set"]:
                session_data["docs_set"].append(file_path)

        # Save
        save_session(session_file, session_data)

    except Exception as e:
        # Fail silently - don't break Claude's workflow
        error_log = SESSIONS_DIR / "hook-errors.log"
        try:
            import traceback
            with open(error_log, "a") as f:
                f.write(f"{datetime.now().isoformat()} track-file-change: {e}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
