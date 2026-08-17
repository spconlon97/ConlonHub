# Conlon Hub Core

Conlon Hub Core is a modular FastAPI application containing the Core service, AI Assistant module, and a safety-restricted TradingBot.

## Current capabilities

- Core health and module-status endpoints
- AI Assistant module status
- Authenticated AI response endpoint with optional OpenAI Responses API provider
- Paper-only TradingBot
- Validated SQLite-backed paper orders
- Local paper-order API
- Automated TradingBot safety tests
- Configurable paper-order value limit
- Simulated paper cash balance and positions
- Caller-priced simulated paper portfolio valuation

## Safety restrictions

- Live trading is disabled in code.
- No exchange connections or API credentials are supported.
- Paper orders are stored locally in SQLite and remain simulated.
- SQLite database files are excluded from Git.
- The `.env` file and virtual environment are excluded from Git.
- A single paper order is limited to `1000.00` by default.
- Rejected orders are not stored.
- Paper accounts start with `10000.00` of virtual cash by default.
- Paper buys cannot exceed available virtual cash.
- Paper sells cannot exceed held simulated positions.
- Portfolio values use caller-supplied simulated prices only.
- No live pricing or market-data connection is used.

## Setup

From the Conlon Hub repository:

```powershell
cd Projects\Core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

On Windows, after storing the OpenAI key with
`scripts\store_openai_key.ps1`, start MARVIS without placing the key in a
plaintext environment variable or repository file:

```powershell
.\scripts\start_marvis.ps1 -Reload
```

The launcher decrypts `%LOCALAPPDATA%\ConlonHub\openai_api_key.dpapi` only into
the MARVIS process environment and removes it when the server exits.

With MARVIS running, open a second PowerShell window in `Projects\Core` and
start a private authenticated conversation:

```powershell
.\scripts\chat_marvis.ps1
```

Type `exit` to finish. The helper decrypts the local MARVIS bearer credential
in memory and automatically keeps the conversation ID for follow-up messages.

## Create the first API credential

Run the local bootstrap command from `Projects/Core`:

```powershell
python -m app.core.auth.bootstrap --name "MARVIS Owner"
```

It creates a principal in `Databases/core_auth.db` and prints one bearer token.
Store that token securely when it is shown; only its verifier is retained and the
token cannot be recovered later. The bootstrap operation is local-only and is not
exposed as an HTTP endpoint.

List non-secret credential metadata or revoke one key without deleting other
principals and credentials:

```powershell
python -m app.core.auth.revoke --list
python -m app.core.auth.revoke --key-id "key-id-before-the-dot"
```

Only the key ID, principal ID, and creation time are listed. Full tokens, secrets,
salts, and verifier digests are never returned.

To enable OpenAI-backed AI responses without the Windows secure launcher, set
the API key in the process environment. The key is never stored by the
application:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

The default model is `gpt-5.6-luna`. Select a different available model with:

```powershell
$env:OPENAI_MODEL = "your-model-id"
```

By default, only the most recent 40 stored messages are sent as context with a
new prompt. Configure an even value from 2 through 200 with:

```powershell
$env:AI_HISTORY_MESSAGE_LIMIT = "40"
```

Prompts are limited to 16,000 characters. The context cap affects only outbound
OpenAI requests; the complete local history remains available for viewing.

Authenticated principals are limited to 10 AI requests per rolling minute by
default. The quota is persisted in SQLite and enforced before any conversation
content is sent externally. Configure a value from 1 through 120 with:

```powershell
$env:AI_REQUESTS_PER_MINUTE = "10"
```

Exceeded requests return HTTP `429` with `Retry-After: 60`.

Without `OPENAI_API_KEY`, `/ai/status` reports `configuration-required` and
authenticated calls to `POST /ai/respond` return HTTP `503`.
The status response includes the selected provider and model, but never returns
the API key.

## AI conversations

`POST /ai/respond` requires the Core bearer credential. The first request can
omit `conversation_id`; the response returns a generated ID. Include that ID in
later requests to continue the same conversation:

```json
{
  "conversation_id": "returned-conversation-id",
  "prompt": "Continue from our previous exchange."
}
```

Conversation messages are stored locally in `Databases/core_ai.db`, isolated by
authenticated principal. When an OpenAI provider is configured, the stored
history for that conversation is sent to the Responses API with the next prompt.

Authenticated users can inspect or permanently delete their stored conversation:

```http
GET /ai/conversations?limit=20&offset=0
GET /ai/conversations/{conversation_id}
DELETE /ai/conversations/{conversation_id}
```

The conversation index returns creation timestamps and message counts without
including message contents. Pagination is bounded to at most 100 conversations.
Deletion removes both the conversation record and all of its stored messages.

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/loaded-modules
http://127.0.0.1:8000/ai/status
http://127.0.0.1:8000/tradingbot/paper-orders
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/tradingbot/paper-account
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The suite covers TradingBot safety behaviour, the Core module registry and loader, the AI Assistant router, and ASGI-level smoke tests exercising the assembled application end to end.
The local paper-order database is created at `Databases/paper_orders.db` from the repository root. It is generated automatically, survives application restarts, and is excluded from Git.

## Paper-order API

Create a simulated order:

```http
POST /tradingbot/paper-orders
Content-Type: application/json
```

Example request:

```json
{
  "symbol": "BTC-GBP",
  "side": "buy",
  "quantity": "0.01",
  "price": "50000"
}
```

List simulated orders:

```http
GET /tradingbot/paper-orders
```
Orders exceeding the configured value limit return HTTP `400` and are not stored.

View the simulated paper account:

```http
GET /tradingbot/paper-account
```
Value the portfolio with caller-supplied simulated prices:

```http
POST /tradingbot/paper-portfolio
Content-Type: application/json
```

Example request:

```json
{
  "prices": {
    "ETH-GBP": "2600"
  }
}
```

This calculation does not retrieve live prices or place orders.

Calculate realized and unrealized profit and loss with caller-supplied simulated prices:

```http
POST /tradingbot/paper-pnl
Content-Type: application/json
```

Example request:

```json
{
  "prices": {
    "ETH-GBP": "2600"
  }
}
```

This calculation does not retrieve live prices or place orders.

These endpoints never place real orders.
