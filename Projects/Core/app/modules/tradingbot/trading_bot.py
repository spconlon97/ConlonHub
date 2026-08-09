from app.modules.base import ModuleBase
from app.modules.tradingbot.config import TradingConfig


class TradingBot(ModuleBase):
    name = "Trading Bot"
    version = "0.2.0"

    def __init__(self, config=None):
        self.config = config or TradingConfig()

    def start(self):
        return self.status()

    def status(self):
        return f"{self.config.mode}-ready"