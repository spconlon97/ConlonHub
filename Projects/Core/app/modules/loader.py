from app.modules.base import ModuleBase
from app.modules.ai.assistant import AIAssistant


loaded_modules = {}


def load_modules():

    modules = [
        AIAssistant()
    ]

    for module in modules:
        loaded_modules[module.name] = {
            "name": module.name,
            "version": module.version,
            "status": module.status()
        }


def get_loaded_modules():

    if not loaded_modules:
        load_modules()

    return {
        "modules": loaded_modules
    }