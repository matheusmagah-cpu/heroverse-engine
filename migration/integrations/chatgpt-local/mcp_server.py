#!/usr/bin/env python3
"""Stdio MCP wrapper of the ChatGPT image runner, for a Claude session on the owner's PC.

  chatgpt_status()                                     LOGGED_IN / NOT_LOGGED_IN
  chatgpt_image(prompt, refs, out_dir, job_id, dry_run) ONE 16:9 image; returns the record (or the stop reason)

Each call runs runner.py in its own process, so the runner's lock, pacing, caps and ledger apply exactly as on the
command line. Register it (on the PC) with:
  claude mcp add heroverse-chatgpt -- C:\\HeroVerse\\chatgpt-runner\\.venv\\Scripts\\python.exe C:\\HeroVerse\\chatgpt-runner\\mcp_server.py
"""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXIT = {0: "OK", 2: "JOB_INVALID", 3: "NOT_LOGGED_IN", 4: "CHALLENGE", 5: "LIMIT", 6: "NO_IMAGE", 7: "GATE",
        8: "RUNNER_BUSY"}


def run(args, timeout=900):
    p = subprocess.run([sys.executable, str(HERE / "runner.py"), *args], capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    lines = [l for l in (p.stdout or "").splitlines() if l.strip()]
    return {"exit": p.returncode, "state": EXIT.get(p.returncode, "ERROR"), "log": lines[-5:]}


def status():
    return run(["status"], timeout=120)


def image(prompt, refs, out_dir, job_id, dry_run=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prompt_file = out / f"{job_id}.prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    res = run(["image", "--prompt", str(prompt_file), "--ref", *refs, "--out", str(out), "--id", job_id]
              + (["--dry-run"] if dry_run else []))
    rec = out / f"{job_id}.json"
    if res["exit"] == 0 and rec.exists() and not dry_run:
        res["record"] = json.loads(rec.read_text(encoding="utf-8"))
    return res


def build():
    try:
        from mcp.server.fastmcp import FastMCP as Server
    except ImportError:   # mcp 2.x
        from mcp.server import MCPServer as Server
    mcp = Server("heroverse-chatgpt", instructions="Unofficial ChatGPT image runner in the owner's own browser session. "
                 "One image at a time; a challenge or usage limit stops it: report, never retry around it.")

    @mcp.tool()
    def chatgpt_status() -> dict:
        """Whether the runner's own Chrome profile is signed in to ChatGPT (the cookie's name only)."""
        return status()

    @mcp.tool()
    def chatgpt_image(prompt: str, refs: list[str], out_dir: str, job_id: str, dry_run: bool = False) -> dict:
        """ONE 16:9 image from the prompt and the reference image files (absolute paths on the PC). Paced: refused
        within 3 min of the last request or past 30 a day."""
        return image(prompt, refs, out_dir, job_id, dry_run)

    return mcp


if __name__ == "__main__":
    build().run()
