# Parsers plugin abstract class

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from abc import ABC, abstractmethod, abstractproperty
from telegram import InlineKeyboardButton,ParseMode

class Message:
    pass

@dataclass
class TextMessage(Message):
    TEXT_MAX_LENGTH = 4096
    text: str
    parse_mode: str = ParseMode.MARKDOWN
    inline_keyboard: Iterable[Iterable[dict]] | Iterable[Iterable[InlineKeyboardButton]] = None
    disable_web_page_preview: bool = False
    disable_notification: bool = False

@dataclass
class PhotoMessage(Message):
    CAPTION_MAX_LENGTH = 200
    photo: str
    text: str = None
    parse_mode: str = ParseMode.MARKDOWN
    inline_keyboard: Iterable[Iterable[dict]] | Iterable[Iterable[InlineKeyboardButton]] = None
    disable_notification: bool = False

class ParserModel(ABC):

    def __init__(self, config):
        self.config = config

    @abstractproperty
    def db_table(self):
        """Bot core will use this property to initialize database"""
        pass

    @abstractmethod
    def new_posts(self) -> Iterable[Message]:
        """Bot core will call this method after each interval to get a list of new posts"""
        pass

    @abstractmethod
    def last_post(self) -> Iterable[Message]:
        """The method that will be call when user sends `/last` command"""
        pass