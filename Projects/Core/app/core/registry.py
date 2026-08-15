from datetime import datetime

from app.modules.loader import get_loaded_modules


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
    loaded = get_loaded_modules()["modules"]

    reconciled = {}
    for key, entry in modules.items():
        loaded_entry = loaded.get(entry["name"])
        if loaded_entry:
            reconciled[key] = {
                **entry,
                "status": loaded_entry["status"],
                "version": loaded_entry["version"]
            }
        else:
            reconciled[key] = dict(entry)

    return {
        "modules": reconciled,
        "updated": datetime.now().isoformat()
    }