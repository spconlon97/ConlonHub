from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from app.modules.tradingbot.paper_account import PaperAccount


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash_balance: Decimal
    position_values: dict[str, Decimal]
    positions_value: Decimal
    total_value: Decimal


class PaperPortfolio:
    def __init__(self, account: PaperAccount):
        self.account = account

    def snapshot(
        self,
        prices: Mapping[str, Decimal],
    ) -> PortfolioSnapshot:
        normalized_prices = {
            symbol.strip().upper(): price
            for symbol, price in prices.items()
        }
        position_values: dict[str, Decimal] = {}

        for symbol, quantity in sorted(
            self.account.positions.items()
        ):
            if symbol not in normalized_prices:
                raise ValueError(
                    f"Missing simulated price for {symbol}."
                )

            price = normalized_prices[symbol]

            if price <= 0:
                raise ValueError(
                    f"Simulated price for {symbol} must be positive."
                )

            position_values[symbol] = quantity * price

        positions_value = sum(
            position_values.values(),
            Decimal("0"),
        )

        return PortfolioSnapshot(
            cash_balance=self.account.cash_balance,
            position_values=position_values,
            positions_value=positions_value,
            total_value=self.account.cash_balance + positions_value,
        )