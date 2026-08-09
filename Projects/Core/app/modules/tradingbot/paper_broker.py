from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder


class PaperBroker:
    def __init__(self, repository=None):
        self.repository = repository
        self._orders = []

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> PaperOrder:
        order = PaperOrder(
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            price=price,
        )

        if self.repository is None:
            self._orders.append(order)
        else:
            self.repository.add(order)

        return order

    def list_orders(self):
        if self.repository is None:
            return tuple(self._orders)

        return self.repository.list_all()