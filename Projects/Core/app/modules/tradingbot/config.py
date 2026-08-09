from dataclasses import dataclass


@dataclass(frozen=True)
class TradingConfig:
    mode: str = "paper"
    live_trading_enabled: bool = False

    def __post_init__(self):
        if self.mode != "paper":
            raise ValueError("Only paper-trading mode is currently supported.")

        if self.live_trading_enabled:
            raise ValueError("Live trading is disabled.")