#!/usr/bin/env python3
"""
Stage files from a specific Claude session for commit.

Usage:
  python stage-my-files.py <session_id>     # Stage files from session
  python stage-my-files.py --list           # List all sessions
  python stage-my-files.py --show <id>      # Show files in a session
  python stage-my-files.py --current        # Auto-detect current session (reads CLAUDE_SESSION_ID env)
  python stage-my-files.py --dry-run [id]   # Preview what would be staged

Can be called by Claude before committing to stage only its own changes.
"""

import json
import sys
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / ".claude" / "sessions"


def list_sessions():
    """List all tracked sessions."""
    if not SESSIONS_DIR.exists():
        print("No sessions tracked yet.")
        return

    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        if f.name.endswith("-errors.log"):
            continue
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "id": data.get("session_id", f.stem)[:12],
                "started": data.get("started", "unknown"),
                "file_count": len(data.get("file_set", []))
            })
        except:
            pass

    if not sessions:
        print("No sessions found.")
        return

    print(f"{'Session ID':<14} {'Started':<20} {'Files':<6}")
    print("-" * 42)
    for s in sorted(sessions, key=lambda x: x["started"], reverse=True):
        started = s["started"][:16].replace("T", " ") if "T" in s["started"] else s["started"]
        print(f"{s['id']:<14} {started:<20} {s['file_count']:<6}")


def show_session(session_id: str):
    """Show files in a session."""
    session_file = find_session_file(session_id)
    if not session_file:
        print(f"Session {session_id} not found.")
        return

    data = json.loads(session_file.read_text())
    files = data.get("file_set", [])
    docs = data.get("docs_set", [])

    print(f"Session: {data.get('session_id', session_id)[:12]}")
    print(f"Started: {data.get('started', 'unknown')}")

    print(f"\nFiles modified ({len(files)}):")
    print("-" * 40)
    for f in files:
        # Check if file exists and has changes
        status = ""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", f],
                capture_output=True, text=True, cwd=PROJECT_ROOT
            )
            if result.stdout.strip():
                status = f" [{result.stdout.strip()[:2]}]"
        except:
            pass
        print(f"  {f}{status}")

    if docs:
        print(f"\nDocs read ({len(docs)}):")
        print("-" * 40)
        for d in docs:
            print(f"  {d}")


def find_session_file(session_id: str) -> Path | None:
    """Find session file by ID (partial match)."""
    if not SESSIONS_DIR.exists():
        return None

    # Try exact match first
    short_id = session_id[:12] if len(session_id) > 12 else session_id
    exact = SESSIONS_DIR / f"{short_id}.json"
    if exact.exists():
        return exact

    # Try prefix match
    for f in SESSIONS_DIR.glob("*.json"):
        if f.stem.startswith(session_id[:8]):
            return f

    return None


def stage_files(session_id: str, dry_run: bool = False):
    """Stage files from a session."""
    session_file = find_session_file(session_id)
    if not session_file:
        print(f"Session {session_id} not found.")
        sys.exit(1)

    data = json.loads(session_file.read_text())
    files = data.get("file_set", [])

    if not files:
        print("No files to stage.")
        return

    # Filter to files that actually have changes
    files_to_stage = []
    for f in files:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", f],
                capture_output=True, text=True, cwd=PROJECT_ROOT
            )
            if result.stdout.strip():
                files_to_stage.append(f)
        except:
            pass

    if not files_to_stage:
        print("All tracked files are already committed or unchanged.")
        return

    if dry_run:
        print(f"Would stage {len(files_to_stage)} files:")
        for f in files_to_stage:
            print(f"  {f}")
        return

    # Stage the files
    for f in files_to_stage:
        try:
            subprocess.run(["git", "add", f], cwd=PROJECT_ROOT, check=True)
            print(f"Staged: {f}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to stage {f}: {e}")

    print(f"\n{len(files_to_stage)} files staged. Run 'git status' to review.")


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] == "--list":
        list_sessions()
    elif args[0] == "--show":
        if len(args) < 2:
            print("Usage: --show <session_id>")
            sys.exit(1)
        show_session(args[1])
    elif args[0] == "--current":
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        if not session_id:
            print("CLAUDE_SESSION_ID not set. Run from within a Claude session.")
            sys.exit(1)
        stage_files(session_id)
    elif args[0] == "--dry-run":
        if len(args) < 2:
            session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        else:
            session_id = args[1]
        if not session_id:
            print("Provide session ID or run from within Claude session.")
            sys.exit(1)
        stage_files(session_id, dry_run=True)
    else:
        stage_files(args[0])


if __name__ == "__main__":
    main()
