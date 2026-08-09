# Conlon Hub Core

Conlon Hub Core is a modular FastAPI application containing the Core service, AI Assistant module, and a safety-restricted TradingBot.

## Current capabilities

- Core health and module-status endpoints
- AI Assistant module status
- Paper-only TradingBot
- Validated SQLite-backed paper orders
- Local paper-order API
- Automated TradingBot safety tests

## Safety restrictions

- Live trading is disabled in code.
- No exchange connections or API credentials are supported.
- Paper orders are stored locally in SQLite and remain simulated.
- SQLite database files are excluded from Git.
- The `.env` file and virtual environment are excluded from Git.

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
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The current suite contains eight TradingBot safety tests.
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

These endpoints never place real orders.