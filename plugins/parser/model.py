# Parsers plugin abstract class

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from abc import ABC, abstractmethod, abstractproperty
from telegram import InlineKeyboardButton, ParseMode, InlineKeyboardMarkup



class MessageModel(ABC):
    pass

@dataclass
class TextMessage(MessageModel):
    MAX_LENGTH = 4096
    text: str
    parse_mode: str = ParseMode.MARKDOWN
    inline_keyboard: Iterable[Iterable[dict]] | Iterable[Iterable[InlineKeyboardButton]] = None
    disable_web_page_preview: bool = False
    disable_notification: bool = False

    def to_dict(self):
        return {
            'text': self.text,
            'parse_mode': self.parse_mode,
            'reply_markup': InlineKeyboardMarkup(self.inline_keyboard),
            'disable_web_page_preview': self.disable_web_page_preview,
            'disable_notification': self.disable_notification,
        }

@dataclass
class PhotoMessage(MessageModel):
    MAX_LENGTH = 200
    photo: str
    text: str = None
    parse_mode: str = ParseMode.MARKDOWN
    inline_keyboard: Iterable[Iterable[dict]] | Iterable[Iterable[InlineKeyboardButton]] = None
    disable_notification: bool = False

    def to_dict(self):
        return {
            'photo': self.photo,
            'caption': self.text,
            'parse_mode': self.parse_mode,
            'reply_markup': InlineKeyboardMarkup(self.inline_keyboard),
            'disable_notification': self.disable_notification,
        }

class VideoMessage(MessageModel):
    MAX_LENGTH = 200
    video: str
    text: str = None
    parse_mode: str = ParseMode.MARKDOWN
    inline_keyboard: Iterable[Iterable[dict]] | Iterable[Iterable[InlineKeyboardButton]] = None
    disable_notification: bool = False

    def to_dict(self):
        return {
            'video': self.video,
            'caption': self.text,
            'parse_mode': self.parse_mode,
            'reply_markup': InlineKeyboardMarkup(self.inline_keyboard),
            'disable_notification': self.disable_notification,
        }

class ParserModel(ABC):

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def new_posts(self) -> Iterable[MessageModel]:
        """Bot core will call this method after each interval to get a list of new posts"""
        pass

    @abstractmethod
    def last_post(self) -> Iterable[MessageModel]:
        """The method that will be call when user sends `/last` command"""
        pass