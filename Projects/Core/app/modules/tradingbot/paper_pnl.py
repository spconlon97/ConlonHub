from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from app.modules.tradingbot.models import OrderSide, PaperOrder


@dataclass(frozen=True)
class PaperPnlSnapshot:
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    average_costs: dict[str, Decimal]


class PaperPnlCalculator:
    def snapshot(
        self,
        orders: Iterable[PaperOrder],
        prices: Mapping[str, Decimal],
    ) -> PaperPnlSnapshot:
        quantities: dict[str, Decimal] = {}
        costs: dict[str, Decimal] = {}
        realized_pnl = Decimal("0")

        for order in orders:
            symbol = order.symbol.strip().upper()
            quantity = quantities.get(symbol, Decimal("0"))
            cost = costs.get(symbol, Decimal("0"))

            if order.side == OrderSide.BUY:
                quantities[symbol] = quantity + order.quantity
                costs[symbol] = cost + order.total
                continue

            if order.quantity > quantity:
                raise ValueError(
                    f"Cannot calculate P&L: insufficient {symbol} position."
                )

            average_cost = cost / quantity
            realized_pnl += (
                order.total - (average_cost * order.quantity)
            )

            remaining_quantity = quantity - order.quantity
            remaining_cost = cost - (average_cost * order.quantity)

            if remaining_quantity == 0:
                quantities.pop(symbol)
                costs.pop(symbol)
            else:
                quantities[symbol] = remaining_quantity
                costs[symbol] = remaining_cost

        normalized_prices = {
            symbol.strip().upper(): price
            for symbol, price in prices.items()
        }
        unrealized_pnl = Decimal("0")
        average_costs: dict[str, Decimal] = {}

        for symbol, quantity in sorted(quantities.items()):
            if symbol not in normalized_prices:
                raise ValueError(
                    f"Missing simulated price for {symbol}."
                )

            price = normalized_prices[symbol]

            if price <= 0:
                raise ValueError(
                    f"Simulated price for {symbol} must be positive."
                )

            average_costs[symbol] = costs[symbol] / quantity
            unrealized_pnl += (
                quantity * price
                - costs[symbol]
            )

        return PaperPnlSnapshot(
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=realized_pnl + unrealized_pnl,
            average_costs=average_costs,
        )