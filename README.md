# personal-finance-mcp

[![Tests](https://github.com/rutvikdumre/personal-finance-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/rutvikdumre/personal-finance-mcp/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-read--only-brightgreen.svg)](https://modelcontextprotocol.io)

Ask Claude (or any MCP client) about your own money: balances, spending, subscriptions, credit cards, loans and investments, across every bank you use.

A self-hosted, **read-only** [MCP](https://modelcontextprotocol.io) server that connects to your accounts through [Plaid](https://plaid.com). Run it on your laptop, or deploy your own private copy in one click. No third-party finance app sits in the middle, and nothing can move money.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/rutvikdumre/personal-finance-mcp)
[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?name=personal-finance-mcp&type=git&repository=github.com/rutvikdumre/personal-finance-mcp&branch=main&builder=dockerfile&instance_type=free&ports=8000;http;/&env[PLAID_ENV]=production&env[PLAID_CLIENT_ID]=&env[PLAID_SECRET]=&env[MCP_AUTH_TOKEN]=)
<!-- Railway needs a published template. Create one at railway.com/new/template from this repo, then uncomment:
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/YOUR-TEMPLATE-CODE?referralCode=&utm_medium=integration&utm_source=button&utm_campaign=personal-finance-mcp)
-->

> Unofficial. Not affiliated with or endorsed by Plaid Inc. You use your own Plaid account and keys.

## What you can ask

- "What's my total balance across all accounts?"
- "How much did I spend on restaurants last month, and where?"
- "Which subscriptions am I still paying for?"
- "When is my credit card due, and what's the APR?"
- "Show my brokerage holdings and dividends this year."
- "Does any bank need me to log in again?"

```
you    : Any subscriptions I'm still paying for?
claude : [calls get_recurring_transactions]
         7 active recurring charges, $142/mo total:
         Netflix $15.99, Spotify $11.99, gym $40, ...
```

## Tools

All 9 tools are read-only. Each returns `{<data>: [...], "warnings": [...]}`, so one broken bank connection doesn't break the whole answer.

| Tool | What it returns |
|---|---|
| `list_accounts` | Every account at every linked bank, with balances |
| `get_balances` | Live current and available balances |
| `get_transactions` | Transactions in a date range (up to 2 years back) |
| `search_transactions` | Keyword search across merchant, description and counterparty |
| `get_recurring_transactions` | Detected subscriptions, bills and paychecks |
| `get_liabilities` | Credit cards, student loans and mortgages: APRs, due dates, minimums |
| `get_investment_holdings` | Current positions with ticker and security details |
| `get_investment_transactions` | Buys, sells and dividends in a date range |
| `get_institutions_status` | Health of each bank connection |

## Quick start (local, about 10 minutes)

You need Python 3.11+ and a free Plaid account.

**1. Get Plaid keys.** Sign up at [dashboard.plaid.com](https://dashboard.plaid.com/signup) and pick the free **Trial** plan (up to 10 bank connections). Under Products, enable **Transactions**, **Liabilities** and **Investments**. Copy your **client ID** and **Production secret** from Developers → Keys.

> Big banks that use OAuth (Chase, Amex, Bank of America, Wells Fargo, Capital One, Schwab and others) must be registered once in the Plaid dashboard. See [Troubleshooting](docs/TROUBLESHOOTING.md#link-flow-errors-with-institution_registration_required). Want to try it first with fake data? Use your **Sandbox** secret, set `PLAID_ENV=sandbox`, and log in to any test bank with `user_good` / `pass_good`.

**2. Install and link your banks.**

```bash
git clone https://github.com/rutvikdumre/personal-finance-mcp.git
cd personal-finance-mcp
python3 setup.py          # Windows: py setup.py
```

`setup.py` creates a virtualenv, asks for your Plaid keys (hidden input), opens a local page where you log in to each bank, and saves everything to `.env`. The page lists every connected bank with its logo, accounts and connection status, so you can see at a glance what's linked and what needs a fresh login. If the `claude` CLI is installed, it also registers the server with Claude Code.

**3. Start the server.**

```bash
.venv/bin/python server.py            # macOS / Linux
.venv\Scripts\python.exe server.py    # Windows
```

It listens on `http://127.0.0.1:8000/mcp`, reachable only from your machine.

**4. Connect your client.**

```bash
claude mcp add --scope user --transport http personal-finance http://127.0.0.1:8000/mcp
```

Then ask: *"list my accounts"*.

## Deploy to the cloud

Hosting it lets you use it from any device without keeping your laptop on. You still link banks locally first, because Plaid's login flow runs in your browser.

1. Do steps 1 and 2 of the quick start. Your `.env` now holds `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` and one `PLAID_TOKEN_<BANK>` per bank.
2. Fork this repo, or use it as is, and click a deploy button:

   | Host | How | Notes |
   |---|---|---|
   | **Render** | [Deploy button](https://render.com/deploy?repo=https://github.com/rutvikdumre/personal-finance-mcp) | Generates `MCP_AUTH_TOKEN` for you. The free plan sleeps after 15 minutes idle, so the first call after that takes about a minute. |
   | **Koyeb** | [Deploy button](https://app.koyeb.com/deploy?name=personal-finance-mcp&type=git&repository=github.com/rutvikdumre/personal-finance-mcp&branch=main&builder=dockerfile&instance_type=free&ports=8000;http;/&env[PLAID_ENV]=production&env[PLAID_CLIENT_ID]=&env[PLAID_SECRET]=&env[MCP_AUTH_TOKEN]=) | Paste your own `MCP_AUTH_TOKEN` (see below). |
   | **Railway** | New Project → Deploy from GitHub repo | Uses `railway.json`. Add the variables under Variables. |
   | **Fly.io, AWS App Runner, Google Cloud Run, a VPS** | Build the `Dockerfile` | Set the same variables. Any host that runs a container works. |

3. Add your variables in the host's dashboard: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`, every `PLAID_TOKEN_*` line from your `.env`, and `MCP_AUTH_TOKEN` (Render creates this one for you). Generate a token with:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. Connect your client with the token. Replace `<url>` with your app's address, for example `https://personal-finance-mcp-xxxx.onrender.com`.

   **Claude Code**

   ```bash
   claude mcp add --scope user --transport http personal-finance <url>/mcp \
     --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
   ```

   **Cursor, VS Code and other clients that take headers**

   ```json
   {
     "mcpServers": {
       "personal-finance": {
         "url": "<url>/mcp",
         "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
       }
     }
   }
   ```

   **Claude Desktop** (`claude_desktop_config.json`, through [mcp-remote](https://www.npmjs.com/package/mcp-remote))

   ```json
   {
     "mcpServers": {
       "personal-finance": {
         "command": "npx",
         "args": ["mcp-remote", "<url>/mcp", "--header", "Authorization:${AUTH_HEADER}"],
         "env": { "AUTH_HEADER": "Bearer <MCP_AUTH_TOKEN>" }
       }
     }
   }
   ```

To link another bank later, run `setup.py` again locally and add the new `PLAID_TOKEN_*` variable to your host. The host restarts with it; no code change needed.

More detail, including Docker commands: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Security

This server can read every account you link, so it's built to fail closed:

- **Read-only.** No tool can move money or change anything at a bank. Write tools are out of scope for this project.
- **Localhost by default.** Without configuration, it binds to `127.0.0.1`.
- **No public server without auth.** If it listens on any other address, it refuses to start unless `MCP_AUTH_TOKEN` (32+ characters) is set. Every MCP request must then send `Authorization: Bearer <token>`. Only `/health`, which returns `ok` and no data, is open.
- **Secrets stay out of the repo and the logs.** `.env` is gitignored (and `chmod 600` on macOS/Linux). Access tokens are wrapped so they print as `<redacted>`.
- **The bank-linking tool never ships.** `link_helper.py` is excluded from the Docker image and refuses to run on Render or Railway.
- **One deployment per person.** Don't share your URL or token. If either leaks, rotate `MCP_AUTH_TOKEN`, and if a Plaid token leaked, remove that bank in the Plaid dashboard.

You are the Plaid customer for your own account, so Plaid's terms apply to you.

## Docs

- [Deployment](docs/DEPLOYMENT.md): every hosting option, Docker, adding banks, re-authenticating
- [Troubleshooting](docs/TROUBLESHOOTING.md): empty results, unsupported banks, slow first calls
- [Architecture](docs/ARCHITECTURE.md): how the code is laid out and why

## Roadmap

- OAuth login, so the server works as a custom connector in claude.ai on web and mobile (those only support OAuth, not bearer tokens)
- One-command re-authentication for banks that need you to log in again

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with `pytest`. They use mocked Plaid calls, so you don't need credentials.

## Credits

Built on [JosueM1109/personal-finance-mcp](https://github.com/JosueM1109/personal-finance-mcp) (MIT). This fork adds bearer-token auth with a safe-by-default bind, guided setup (`setup.py`), one-click deploys, and hermetic tests.

## License

[MIT](LICENSE)
