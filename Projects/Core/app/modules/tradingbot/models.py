from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    FILLED = "filled"


@dataclass(frozen=True)
class PaperOrder:
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    status: OrderStatus = OrderStatus.FILLED

    def __post_init__(self):
        if not self.symbol.strip():
            raise ValueError("Symbol is required.")

        if self.quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if self.price <= 0:
            raise ValueError("Price must be greater than zero.")

    @property
    def total(self):
        return self.quantity * self.price