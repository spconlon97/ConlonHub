from app.modules.base import ModuleBase


class AIAssistant(ModuleBase):
    name = "AI Assistant"
    version = "0.1.0"

    def start(self):
        return self.status()

    def status(self):
        return "online"