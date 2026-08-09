from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TradingConfig:
    mode: str = "paper"
    live_trading_enabled: bool = False
    max_order_value: Decimal = Decimal("1000.00")

    def __post_init__(self):
        if self.mode != "paper":
            raise ValueError("Only paper-trading mode is currently supported.")

        if self.live_trading_enabled:
            raise ValueError("Live trading is disabled.")

        if self.max_order_value <= 0:
            raise ValueError("Maximum order value must be greater than zero.")