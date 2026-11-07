from decimal import Decimal, InvalidOperation

from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import CapabilityRegistry
from app.modules.loader import get_loaded_modules, get_module_instance
from app.modules.tradingbot.models import OrderSide, PaperOrder


def _system_modules():
    return get_loaded_modules()


def _trading_status():
    trading_bot = get_module_instance("Trading Bot")

    return {
        "name": trading_bot.name,
        "version": trading_bot.version,
        "status": trading_bot.status(),
    }


def _trading_paper_account():
    trading_bot = get_module_instance("Trading Bot")
    account = trading_bot.account

    return {
        "starting_cash": str(account.starting_cash),
        "cash_balance": str(account.cash_balance),
        "positions": {
            symbol: str(quantity)
            for symbol, quantity in sorted(account.positions.items())
        },
    }


def _trading_paper_orders():
    trading_bot = get_module_instance("Trading Bot")

    return [
        {
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": str(order.quantity),
            "price": str(order.price),
            "status": order.status.value,
            "total": str(order.total),
        }
        for order in trading_bot.list_paper_orders()
    ]


def _decimal(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{label} must be a number.")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError(f"{label} must be a number.") from error
    return number


def _paper_order(symbol, side, quantity, price) -> PaperOrder:
    """Parse model-supplied arguments into a validated (unplaced) paper order."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Symbol is required.")
    try:
        order_side = OrderSide(str(side).strip().lower())
    except ValueError as error:
        raise ValueError("Side must be 'buy' or 'sell'.") from error

    return PaperOrder(
        symbol=symbol.strip().upper(),
        side=order_side,
        quantity=_decimal(quantity, "Quantity"),
        price=_decimal(price, "Price"),
    )


def _summarize_paper_order(symbol, side, quantity, price):
    order = _paper_order(symbol, side, quantity, price)
    trading_bot = get_module_instance("Trading Bot")

    # Refuse clearly invalid orders before asking a human; all of these are
    # checked again by place_paper_order when the approved request runs.
    if order.total > trading_bot.config.max_order_value:
        raise ValueError(
            f"Paper order value {order.total} exceeds maximum of "
            f"{trading_bot.config.max_order_value}."
        )
    trading_bot.account.validate_order(order)

    return (
        f"Paper {order.side.value.upper()} {order.quantity} {order.symbol} at "
        f"{order.price} (total {order.total} paper cash). "
        "Simulated only, no real money."
    )


def _place_paper_order(symbol, side, quantity, price):
    order = _paper_order(symbol, side, quantity, price)
    trading_bot = get_module_instance("Trading Bot")
    placed = trading_bot.place_paper_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
    )

    return {
        "order": {
            "symbol": placed.symbol,
            "side": placed.side.value,
            "quantity": str(placed.quantity),
            "price": str(placed.price),
            "status": placed.status.value,
            "total": str(placed.total),
        },
        "cash_balance": str(trading_bot.account.cash_balance),
    }


def build_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()

    registry.register(
        Capability(
            name="system.modules",
            description="Return the currently loaded Conlon Hub modules and their status.",
            access=CapabilityAccess.READ,
            handler=_system_modules,
        )
    )

    registry.register(
        Capability(
            name="trading.status",
            description="Return the current Trading Bot status.",
            access=CapabilityAccess.READ,
            handler=_trading_status,
        )
    )

    registry.register(
        Capability(
            name="trading.paper_account",
            description="Return the current Trading Bot paper account state.",
            access=CapabilityAccess.READ,
            handler=_trading_paper_account,
        )
    )

    registry.register(
        Capability(
            name="trading.paper_orders",
            description="Return the Trading Bot paper order history.",
            access=CapabilityAccess.READ,
            handler=_trading_paper_orders,
        )
    )

    registry.register(
        Capability(
            name="trading.place_paper_order",
            description=(
                "Propose a simulated paper order (side 'buy' or 'sell'; quantity "
                "and price as numbers). Requires human approval; never real money."
            ),
            access=CapabilityAccess.ACTION,
            handler=_place_paper_order,
            summarize=_summarize_paper_order,
        )
    )

    return registry
