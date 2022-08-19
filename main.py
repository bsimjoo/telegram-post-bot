import logging
import jstyleson
import importlib
from peewee import *
from logging.handlers import TimedRotatingFileHandler
from telegram import *
from telegram.ext import Updater, Handler, CallbackContext
from colored_log import ColoredLog
from os.path import exists, join as path_join
from decorators import HandlersDecorator, Auth
from threading import Timer

from plugins.parser.model import ParserModel ,MessageModel, TextMessage, PhotoMessage, VideoMessage

# Configure logger
CONFIG_FILE = "config.jsonc" if exists("config.jsonc") else "config.default.jsonc"

config:dict = jstyleson.load(open(CONFIG_FILE))
logFormatter = logging.Formatter("%(asctime)s  %(name)-12.12s L%(lineno)-4.4d  %(levelname)-7.7s: %(message)s")
handlers = []
if log_dir:=config.get('log-dir'):
    fileHandler = TimedRotatingFileHandler(filename=path_join(log_dir, 'Telegram-post-bot.log'), when='midnight', interval=1, backupCount=7)
    fileHandler.setFormatter(logFormatter)
    handlers.append(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(ColoredLog())
handlers.append(consoleHandler)
level = logging._nameToLevel.get(config.get('log-level','INFO').upper(),logging.INFO)
logging.basicConfig(level=level, handlers=handlers)
logger = logging.getLogger('Telegram-post-bot')
DEBUG = config.get('debug',False)       #didn't used

# ===========================
# Database
# ===========================

db_file = config.get('database', 'database.sqlite')
db = SqliteDatabase(db_file)

class Admin(Model):
    id = IntegerField(unique=True)
    username = CharField()
    first_name = CharField()
    last_name = CharField(null=True)
    language = CharField(null=True)
    state = IntegerField(default=0)
    privilege = IntegerField(default=0) # 0: admin, 1: super admin
    class Meta:
        database = db

class Chatdb(Model):
    id = IntegerField(unique=True)
    type = CharField(null=True)
    title = CharField(null=True)
    username = CharField(null=True)
    first_name = CharField(null=True)
    last_name = CharField(null=True)
    type = CharField()
    members_count = IntegerField(default=1)
    active = BooleanField(default=True)
    class Meta:
        database = db

class BotData(Model):
    interval = IntegerField(default=120)
    super_admin_id = IntegerField(null=True)

    class Meta:
        database = db

# ===========================
# Import parser plugins
# ===========================
cfg_parser = config['parser']
logger.info("Loading parser (%s) plugin...", cfg_parser)
parser_config = config['parser-config']
parser_module = importlib.import_module('.'.join(['plugins','parser', cfg_parser, 'plugin']))
parser_db_table = parser_module.db_table
logger.info("initlizing parser database...")
parser_module.db_proxy.initialize(db)

db.connect()
for table in (Admin, Chatdb, BotData):
    if not db.table_exists(table):
        db.create_tables([table])
if not db.table_exists(parser_db_table):
    db.create_tables([parser_db_table])

def settings():
    return BotData.get_or_create()[0]

# ===========================
# Telegram Bot
# ===========================
logger.info("initlizing parser...")
parser:ParserModel = parser_module.Parser(parser_config)

if 'proxy-url' in config:
    updater = Updater(token=config['token'], use_context=True, request_kwargs={'proxy_url': config['proxy-url']})
else:
    updater = Updater(token=config.get('telegram-token'), use_context=True)

decorators = HandlersDecorator(updater.dispatcher)

def admins_list():
    return [admin.id for admin in Admin.select()]

def send_message(message:MessageModel, chat_id:int):
    if isinstance(message,TextMessage):
        return updater.bot.send_message(chat_id=chat_id,**message.to_dict())
    elif isinstance(message,PhotoMessage):
        return updater.bot.send_photo(chat_id=chat_id, **message.to_dict())
    elif isinstance(message,VideoMessage):
        return updater.bot.send_video(chat_id=chat_id, **message.to_dict())
    updater.bot.send_message()

def send_new_posts():
    logger.debug("Sending new posts...")
    messages = parser.new_posts()
    if messages:
        logger.info("got %d messages", len(messages))
        for chat in Chatdb.select().where(Chatdb.active == True):
            logger.info("Sending messages to %s", chat.title)
            for message in messages:
                send_message(message, chat.id)
    else:
        logger.debug("No new posts")

def check_new_posts():
    logger.debug("Checking new posts...")
    send_new_posts()
    logger.debug("setting timer...")
    timer = Timer(settings().interval, check_new_posts)
    timer.start()
    logger.debug("timer set for %d seconds", settings().interval)

@decorators.CommandHandler
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat = update.message.chat
    
    if chat.type == 'private' and len(context.args) > 0:
        if context.args[0] == config['token']:
            Admin.create(id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name, language=user.language_code, state=0, privilege=1)
            update.message.reply_text("You are now a super admin.")
        #TODO: add admins registration
    
    q = Chatdb.select().where(Chatdb.id == chat.id)
    if q.exists():
        update.message.reply_text("You are already registered.")        #TODO: configurable messages
        return
    
    update.message.reply_text("You are now registered.")
    members_count = chat.get_member_count()
    Chatdb.create(id=chat.id, type=chat.type, title=chat.title, username=chat.username, first_name=chat.first_name, last_name=chat.last_name, members_count=members_count-1)  # -1 for bot

@decorators.CommandHandler
@Auth(admins_list)      # sending this method to keep this authorization up to date
def members_count(update: Update, context: CallbackContext):
    chats_count = Chatdb.select().count()
    total_count = sum(chat.members_count for chat in Chatdb.select())
    update.message.reply_text("There are {} chats and {} members in total.".format(chats_count, total_count))

#TODO: remove this test message handler
@decorators.MessageHandler()
def echo(update: Update, context: CallbackContext):
    update.message.reply_text(update.message.text)

updater.start_polling()
check_new_posts()
updater.idle()