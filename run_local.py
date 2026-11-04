"""Start the server on this machine only (127.0.0.1), with .env loaded.

Kept for older setups; `python server.py` does the same thing now.
"""
import os

os.environ.setdefault("HOST", "127.0.0.1")

from server import main  # noqa: E402

main()
