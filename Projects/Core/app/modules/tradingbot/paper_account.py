from dataclasses import dataclass, field
from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder


@dataclass
class PaperAccount:
    starting_cash: Decimal = Decimal("10000.00")
    cash_balance: Decimal = field(init=False)
    positions: dict[str, Decimal] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self):
        if self.starting_cash <= 0:
            raise ValueError("Starting paper cash must be greater than zero.")

        self.cash_balance = self.starting_cash

    def position_for(self, symbol: str) -> Decimal:
        normalized_symbol = symbol.strip().upper()
        return self.positions.get(normalized_symbol, Decimal("0"))

    def apply_order(self, order: PaperOrder):
        symbol = order.symbol.strip().upper()

        if order.side == OrderSide.BUY:
            if order.total > self.cash_balance:
                raise ValueError(
                    f"Paper order value {order.total} exceeds "
                    f"available cash {self.cash_balance}."
                )

            self.cash_balance -= order.total
            self.positions[symbol] = (
                self.position_for(symbol) + order.quantity
            )
            return

        available_quantity = self.position_for(symbol)

        if order.quantity > available_quantity:
            raise ValueError(
                f"Cannot sell {order.quantity} {symbol}; "
                f"only {available_quantity} available."
            )

        self.cash_balance += order.total
        remaining_quantity = available_quantity - order.quantity

        if remaining_quantity == 0:
            self.positions.pop(symbol)
        else:
            self.positions[symbol] = remaining_quantity