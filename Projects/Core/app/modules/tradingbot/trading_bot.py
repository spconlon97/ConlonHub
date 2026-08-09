from decimal import Decimal

from app.modules.base import ModuleBase
from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_broker import PaperBroker


class TradingBot(ModuleBase):
    name = "Trading Bot"
    version = "0.4.0"

    def __init__(self, config=None, broker=None):
        self.config = config or TradingConfig()
        self.broker = broker or PaperBroker()

    def start(self):
        return self.status()

    def status(self):
        return f"{self.config.mode}-ready"

    def place_paper_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> PaperOrder:
        return self.broker.place_order(symbol, side, quantity, price)

    def list_paper_orders(self):
        return self.broker.list_orders()