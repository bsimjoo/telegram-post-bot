from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackContext
from functools import wraps
from logging import getLogger

class HandlersDecorator(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.logger = getLogger('handlers')

    def CommandHandler(self,command):
        def wrapper(func):
            self.logger.debug('CommandHandler: %s', command)
            self.dispatcher.add_handler(CommandHandler(command, func))
            return func
        if callable(command):
            func = command
            command = func.__name__
            return wrapper(func)
        return wrapper

    def MessageHandler(self, filters = Filters.text):
        def wrapper(func):
            self.logger.debug('MessageHandler: %s', filters)
            self.dispatcher.add_handler(MessageHandler(filters, func))
            return func
        return wrapper

def Auth(authorized: callable):
    def wrapper(func):
        @wraps(func)
        def wrapped(update: Update, context: CallbackContext):
            user = update.message.from_user
            if user.id not in authorized():
                update.message.reply_text("You are not authorized to use this command.")
                return
            return func(update, context)
        return wrapped
    return wrapper