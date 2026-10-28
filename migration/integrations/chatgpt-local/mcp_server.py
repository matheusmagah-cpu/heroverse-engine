#!/usr/bin/env python3
"""Stdio MCP over app_driver.py (the owner's ChatGPT desktop app), for a Claude session on the PC.

  chatgpt_app_status()                                   APP_READY / APP_NOT_RUNNING
  chatgpt_app_image(prompt, refs, out_dir, job_id)       ONE 16:9 image; the record, or the stop reason

Each call runs app_driver.py in its own process, so its lock, pacing, caps and ledger apply. Register on the PC with:
  claude mcp add heroverse-chatgpt -- C:\\HeroVerse\\chatgpt-runner\\.venv\\Scripts\\python.exe C:\\HeroVerse\\chatgpt-runner\\mcp_server.py
"""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXIT = {0: "OK", 2: "JOB_INVALID", 4: "VERIFICATION", 5: "LIMIT", 6: "NO_IMAGE", 7: "GATE", 8: "BUSY",
        9: "APP_NOT_RUNNING"}


def run(args, timeout=1200):
    p = subprocess.run([sys.executable, str(HERE / "app_driver.py"), *args], capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    lines = [l for l in (p.stdout or "").splitlines() if l.strip()]
    return {"exit": p.returncode, "state": EXIT.get(p.returncode, "ERROR"), "log": lines[-5:]}


def image(prompt, refs, out_dir, job_id):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prompt_file = out / f"{job_id}.prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    res = run(["image", "--prompt", str(prompt_file), "--ref", *refs, "--out", str(out), "--id", job_id])
    rec = out / f"{job_id}.json"
    if res["exit"] == 0 and rec.exists():
        res["record"] = json.loads(rec.read_text(encoding="utf-8"))
    return res


def build():
    try:
        from mcp.server.fastmcp import FastMCP as Server
    except ImportError:   # mcp 2.x
        from mcp.server import MCPServer as Server
    mcp = Server("heroverse-chatgpt", instructions="The owner's ChatGPT desktop app driven for one image at a time. "
                 "A verification or usage limit stops it: report it, never retry around it.")

    @mcp.tool()
    def chatgpt_app_status() -> dict:
        """Whether the ChatGPT app is open with its composer."""
        return run(["status"], timeout=120)

    @mcp.tool()
    def chatgpt_app_image(prompt: str, refs: list[str], out_dir: str, job_id: str) -> dict:
        """ONE 16:9 image in a new chat of the ChatGPT app, from the prompt and reference image files (absolute paths
        on the PC). Refused within 3 min of the last request or past 30 a day."""
        return image(prompt, refs, out_dir, job_id)

    return mcp


if __name__ == "__main__":
    build().run()
