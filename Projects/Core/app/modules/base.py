from abc import ABC, abstractmethod


class ModuleBase(ABC):

    name = "Unnamed Module"
    version = "0.1.0"

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def status(self):
        pass