from datetime import datetime


modules = {
    "core": {
        "name": "Core",
        "status": "online",
        "version": "0.1.0"
    },

    "ai": {
        "name": "AI Assistant",
        "status": "planned",
        "version": "0.1.0"
    },

    "trading": {
        "name": "Trading Bot",
        "status": "planned",
        "version": "0.1.0"
    },

    "home": {
        "name": "Home Automation",
        "status": "planned",
        "version": "0.1.0"
    }
}


def get_modules():
    return {
        "modules": modules,
        "updated": datetime.now().isoformat()
    }