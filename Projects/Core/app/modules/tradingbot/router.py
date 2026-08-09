from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.trading_bot import TradingBot


router = APIRouter(prefix="/tradingbot", tags=["TradingBot"])
trading_bot = TradingBot()


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)


def serialize_order(order: PaperOrder):
    return {
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": str(order.quantity),
        "price": str(order.price),
        "status": order.status.value,
        "total": str(order.total),
    }


@router.post("/paper-orders")
def place_paper_order(request: PaperOrderRequest):
    order = trading_bot.place_paper_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        price=request.price,
    )
    return {"order": serialize_order(order)}


@router.get("/paper-orders")
def list_paper_orders():
    return {
        "orders": [
            serialize_order(order)
            for order in trading_bot.list_paper_orders()
        ]
    }