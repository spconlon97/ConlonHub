from fastapi import FastAPI
from datetime import datetime
from app.core.registry import get_modules
from app.core.config import settings
from app.modules.loader import get_loaded_modules


app = FastAPI(
    title=settings.app_name,
    version=settings.version
)


@app.get("/")
def home():
    return {
        "system": settings.app_name,
        "module": "Core",
        "environment": settings.environment,
        "status": "online",
        "time": datetime.now().isoformat()
    }

@app.get("/modules")
def module_list():
    return get_modules()


@app.get("/loaded-modules")
def loaded_modules():
    return get_loaded_modules()