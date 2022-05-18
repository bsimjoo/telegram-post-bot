# Parsers plugin abstract class

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

@dataclass
class TextMessage:
    text: str
    inline_keyboard: Iterable[Iterable[dict]] = None

class ParserModel:
    def __init__(self, config:dict):
        self.config = config

    def parse_page(self, raw_data:str) -> Iterable(Post):
        raise NotImplementedError