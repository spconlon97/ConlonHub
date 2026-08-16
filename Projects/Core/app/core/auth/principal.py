from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    principal_id: str
    name: str

    def __post_init__(self):
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id must be a non-empty string.")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
