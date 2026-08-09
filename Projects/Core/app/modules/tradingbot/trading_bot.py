from app.modules.base import ModuleBase


class TradingBot(ModuleBase):
    name = "Trading Bot"
    version = "0.1.0"

    def start(self):
        return "ready"

    def status(self):
        return "ready"