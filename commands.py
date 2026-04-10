from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Command:
    name: str
    callback: Callable[[list[str]], None]
    description: str
    shortcuts: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
