from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import CapabilityRegistry
from app.modules.loader import get_loaded_modules, get_module_instance


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

    return registry
