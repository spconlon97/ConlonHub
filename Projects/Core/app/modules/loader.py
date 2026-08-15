from app.modules.ai.assistant import AIAssistant
from app.modules.tradingbot.trading_bot import TradingBot


loaded_modules = {}
module_instances = {}


def load_modules():
    modules = [
        AIAssistant(),
        TradingBot(),
    ]

    for module in modules:
        module.start()

    for module in modules:
        module_instances[module.name] = module
        loaded_modules[module.name] = {
            "name": module.name,
            "version": module.version,
            "status": module.status(),
        }


def _ensure_loaded():
    if not loaded_modules:
        load_modules()


def get_loaded_modules():
    _ensure_loaded()

    return {
        "modules": loaded_modules
    }


def get_module_instance(name):
    _ensure_loaded()

    return module_instances.get(name)