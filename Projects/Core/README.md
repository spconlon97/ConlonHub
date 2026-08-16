# Conlon Hub Core

Conlon Hub Core is a modular FastAPI application containing the Core service, AI Assistant module, and a safety-restricted TradingBot.

## Current capabilities

- Core health and module-status endpoints
- AI Assistant module status
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

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/loaded-modules
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