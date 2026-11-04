#!/usr/bin/env python3
"""
One-time local setup for personal-finance-mcp (Plaid -> Claude), read-only.

Run from the repo root:
       python3 setup.py          (macOS / Linux)
       py setup.py               (Windows)

Needs: Python 3.11+, plus your Plaid client_id and secret
(dashboard.plaid.com -> Developers -> Keys).

What it does:
  1. (repo is already cloned: you're in it)
  2. Creates a virtualenv and installs dependencies
  3. Asks for your Plaid keys (hidden input) and writes .env
  4. Starts the Plaid Link helper so you can log in to each bank,
     and saves each bank's access token into .env automatically
  5. Registers the server with Claude Code if the `claude` CLI is installed

Re-run it any time to link another bank.
"""
from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

DEST = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
VENV_PY = DEST / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
ENV_FILE = DEST / ".env"
TOKEN_RE = re.compile(r"(PLAID_TOKEN_[A-Z0-9_]+)=(access-\S+)")

def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd: list[str], **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def write_env(env: dict[str, str]) -> None:
    ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    if not IS_WIN:
        os.chmod(ENV_FILE, 0o600)  # readable by you only


def main() -> None:
    if sys.version_info < (3, 11):
        sys.exit("Python 3.11+ is required. Install it from python.org and re-run.")
    # 2. Virtualenv + deps
    if not VENV_PY.exists():
        step("Creating virtualenv")
        run([sys.executable, "-m", "venv", str(DEST / ".venv")])
    step("Installing dependencies (takes a minute)")
    run([str(VENV_PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(DEST / "requirements.txt")])

    # 3. Plaid keys
    env = read_env()
    if env.get("PLAID_CLIENT_ID") and env.get("PLAID_SECRET"):
        step("Plaid keys already in .env, keeping them")
    else:
        step("Paste your Plaid keys (input is hidden)")
        env["PLAID_CLIENT_ID"] = getpass.getpass("  PLAID_CLIENT_ID: ").strip()
        env["PLAID_SECRET"] = getpass.getpass("  PLAID_SECRET (Production): ").strip()
        if not env["PLAID_CLIENT_ID"] or not env["PLAID_SECRET"]:
            sys.exit("Both keys are required.")
    env.setdefault("PLAID_ENV", "production")
    write_env(env)

    # 5. Link banks
    step("Starting the bank-link page at http://localhost:8765")
    print("  In the browser: click 'Link a bank' and log in. Repeat for each bank or card.")
    print("  Tokens are saved to .env automatically. Come back here and press Enter when done.")
    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "link_helper:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd=DEST, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    found: dict[str, str] = {}

    def reader() -> None:
        assert proc.stdout
        for line in proc.stdout:
            m = TOKEN_RE.search(line)
            if m:
                found[m.group(1)] = m.group(2)
                env.update({m.group(1): m.group(2)})
                write_env(env)
                print(f"\n  Saved {m.group(1)}  ✓  (link another bank, or press Enter to finish)", flush=True)
            elif "error" in line.lower() or "traceback" in line.lower():
                print("  [link helper] " + line.rstrip(), flush=True)

    threading.Thread(target=reader, daemon=True).start()
    time.sleep(3)
    if proc.poll() is not None:
        sys.exit("Link helper failed to start. Check that your Plaid keys are correct.")
    webbrowser.open("http://localhost:8765")
    input()
    proc.terminate()

    linked = [k for k in env if k.startswith("PLAID_TOKEN_")]
    if not linked:
        print("\n  No banks linked yet. Re-run this script any time to link them.")
    else:
        print(f"\n  Linked: {', '.join(k.removeprefix('PLAID_TOKEN_') for k in linked)}")

    # 6. Register with Claude Code
    url = "http://127.0.0.1:8000/mcp"
    start_cmd = f'"{VENV_PY}" "{DEST / "server.py"}"'
    if shutil.which("claude"):
        step("Registering with Claude Code")
        subprocess.run(["claude", "mcp", "add", "--scope", "user", "--transport", "http",
                        "personal-finance", url])

    step("Done")
    print(f"""
  Start the server (leave this terminal open):
    {start_cmd}

  Claude Code:    already registered if the `claude` CLI was found; otherwise run
                  claude mcp add --scope user --transport http personal-finance {url}
  Claude Desktop: Settings -> Connectors / Developer -> add a local MCP server at {url}

  Then ask Claude: "list my accounts" or "what did I spend on dining last month?"
  Re-run this script to link more banks.

  Deploying to the cloud? Copy PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV and
  every PLAID_TOKEN_* line from {ENV_FILE} into your host's environment variables.
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
