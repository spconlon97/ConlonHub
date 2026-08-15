from app.modules.ai.assistant import AIAssistant
from app.modules.tradingbot.trading_bot import TradingBot


loaded_modules = {}


def load_modules():
    modules = [
        AIAssistant(),
        TradingBot(),
    ]

    for module in modules:
        module.start()

    for module in modules:
        loaded_modules[module.name] = {
            "name": module.name,
            "version": module.version,
            "status": module.status(),
        }


def get_loaded_modules():
    if not loaded_modules:
        load_modules()

    return {
        "modules": loaded_modules
    }