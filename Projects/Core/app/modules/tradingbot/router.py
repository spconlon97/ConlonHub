from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.trading_bot import TradingBot
from app.modules.tradingbot.paper_broker import PaperBroker
from app.modules.tradingbot.sqlite_repository import (
    SqlitePaperOrderRepository,
)
from app.modules.loader import register_module_instance


router = APIRouter(prefix="/tradingbot", tags=["TradingBot"])
database_path = (
    Path(__file__).resolve().parents[5]
    / "Databases"
    / "paper_orders.db"
)
repository = SqlitePaperOrderRepository(database_path)
broker = PaperBroker(repository=repository)
trading_bot = TradingBot(broker=broker)
register_module_instance(trading_bot)


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)


class PaperPortfolioRequest(BaseModel):
    prices: dict[str, Decimal]


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
    try:
        order = trading_bot.place_paper_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {"order": serialize_order(order)}


@router.get("/paper-orders")
def list_paper_orders():
    return {
        "orders": [
            serialize_order(order)
            for order in trading_bot.list_paper_orders()
        ]
    }
@router.get("/paper-account")
def get_paper_account():
    return {
        "starting_cash": str(
            trading_bot.account.starting_cash
        ),
        "cash_balance": str(
            trading_bot.account.cash_balance
        ),
        "positions": {
            symbol: str(quantity)
            for symbol, quantity in sorted(
                trading_bot.account.positions.items()
            )
        },
    }
@router.post("/paper-portfolio")
def value_paper_portfolio(
    request: PaperPortfolioRequest,
):
    try:
        snapshot = trading_bot.paper_portfolio_snapshot(
            request.prices
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "portfolio": {
            "cash_balance": str(snapshot.cash_balance),
            "position_values": {
                symbol: str(value)
                for symbol, value in sorted(
                    snapshot.position_values.items()
                )
            },
            "positions_value": str(
                snapshot.positions_value
            ),
            "total_value": str(snapshot.total_value),
        }
    }