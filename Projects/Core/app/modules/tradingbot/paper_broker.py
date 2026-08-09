from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder


class PaperBroker:
    def __init__(self):
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
        self._orders.append(order)
        return order

    def list_orders(self):
        return tuple(self._orders)