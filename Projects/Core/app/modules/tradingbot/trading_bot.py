from decimal import Decimal

from app.modules.base import ModuleBase
from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_account import PaperAccount
from app.modules.tradingbot.paper_broker import PaperBroker
from app.modules.tradingbot.paper_pnl import PaperPnlCalculator
from app.modules.tradingbot.paper_portfolio import PaperPortfolio


class TradingBot(ModuleBase):
    name = "Trading Bot"
    version = "0.7.0"

    def __init__(
        self,
        config=None,
        broker=None,
        account=None,
    ):
        self.config = config or TradingConfig()
        self.broker = broker or PaperBroker()
        self.account = account or PaperAccount(
            starting_cash=self.config.starting_cash,
        )

        if account is None:
            for existing_order in self.broker.list_orders():
                self.account.apply_order(existing_order)

        self.portfolio = PaperPortfolio(self.account)
        self.pnl_calculator = PaperPnlCalculator()

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
        candidate_order = PaperOrder(
            symbol=symbol.strip().upper(),
            side=side,
            quantity=quantity,
            price=price,
        )

        if candidate_order.total > self.config.max_order_value:
            raise ValueError(
                f"Paper order value {candidate_order.total} exceeds "
                f"maximum of {self.config.max_order_value}."
            )

        self.account.validate_order(candidate_order)

        order = self.broker.place_order(
            candidate_order.symbol,
            candidate_order.side,
            candidate_order.quantity,
            candidate_order.price,
        )
        self.account.apply_order(order)

        return order

    def list_paper_orders(self):
        return self.broker.list_orders()

    def paper_portfolio_snapshot(
        self,
        prices: dict[str, Decimal],
    ):
        return self.portfolio.snapshot(prices)

    def paper_pnl_snapshot(
        self,
        prices: dict[str, Decimal],
    ):
        return self.pnl_calculator.snapshot(
            self.broker.list_orders(),
            prices,
        )