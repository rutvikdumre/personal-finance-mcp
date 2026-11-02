"""Start the finance MCP on localhost only, with .env loaded.

Upstream server.py binds 0.0.0.0 (every device on your network, no auth) and
doesn't load .env. This wrapper fixes both without modifying upstream code.
"""
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import server  # noqa: E402  (registers the read-only tools)

server.mcp.run(transport="http", host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
