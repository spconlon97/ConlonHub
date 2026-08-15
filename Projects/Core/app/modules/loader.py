from app.modules.ai.assistant import AIAssistant
from app.modules.tradingbot.trading_bot import TradingBot


loaded_modules = {}
module_instances = {}


def _module_classes():
    return [AIAssistant, TradingBot]


def register_module_instance(module):
    module.start()

    module_instances[module.name] = module
    loaded_modules[module.name] = {
        "name": module.name,
        "version": module.version,
        "status": module.status(),
    }


def load_modules():
    pending = [
        module_class()
        for module_class in _module_classes()
        if module_class.name not in module_instances
    ]

    for module in pending:
        module.start()

    for module in pending:
        module_instances[module.name] = module
        loaded_modules[module.name] = {
            "name": module.name,
            "version": module.version,
            "status": module.status(),
        }


def _ensure_loaded():
    if any(cls.name not in module_instances for cls in _module_classes()):
        load_modules()


def get_loaded_modules():
    _ensure_loaded()

    return {
        "modules": loaded_modules
    }


def get_module_instance(name):
    _ensure_loaded()

    return module_instances.get(name)