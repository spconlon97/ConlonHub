---
paths:
  - "app/modules/tradingbot/**"
  - "tests/**tradingbot*"
  - "tests/**paper*"
  - "app/modules/ai/**"
---

# TradingBot module: paper trading only

Preserve the existing safety restrictions of `app/modules/tradingbot`:

- No live trading and no exchange connections or exchange credentials.
- Keep order value limits and cash/position limits in place.
- Prices are caller-supplied only; do not add market-data fetching.
- MARVIS/AI trading language stays paper-only.
