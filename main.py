from cmath import log
import logging
from logging.handlers import TimedRotatingFileHandler
import json
from telegram import *
from telegram.ext import Application, ApplicationBuilder, Updater, CommandHandler, MessageHandler
from colored_log import ColoredLog
from os.path import exists, join as path_join

CONFIG_FILE = "config.json" if exists("config.json") else "config.default.json"

class TelegramPostBot:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        app_builder = ApplicationBuilder.token(config['token'])
        if proxy_url := config.get('proxy_url'):
            app_builder.proxy_url(proxy_url)
        self.app = app_builder.build()

def main():
    config = json.load(open(CONFIG_FILE))
    logFormatter = logging.Formatter("%(asctime)s  %(name)-12.12s L%(lineno)-4.4d  %(levelname)-7.7s: %(message)s")
    log_dir = config.get('log-dir')
    handlers = []
    if log_dir is not None:
        fileHandler = TimedRotatingFileHandler(filename=path_join(log_dir, 'Telegram-post-bot.log'), when='midnight', interval=1, backupCount=7)
        fileHandler.setFormatter(logFormatter)
        handlers.append(fileHandler)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(ColoredLog())
    handlers.append(consoleHandler)
    level = logging._nameToLevel.get(config.get('log-level','INFO').upper(),logging.INFO)
    logging.basicConfig(level=level, handlers=handlers)

if __name__ == '__main__':
    main()