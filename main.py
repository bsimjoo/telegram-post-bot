import logging
import json
import importlib
from peewee import *
from logging.handlers import TimedRotatingFileHandler
from telegram import *
from telegram.ext import Updater, Handler, CallbackContext
from colored_log import ColoredLog
from os.path import exists, join as path_join
from decorators import HandlersDecorator, Auth

# Configure logger
CONFIG_FILE = "config.json" if exists("config.json") else "config.default.json"

config = json.load(open(CONFIG_FILE))
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

# ===========================
# Database
# ===========================

db_file = config.get('database', 'database.sqlite')
db_exists = exists(db_file)
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

class Chat(Model):
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
    source = CharField()
    latest_post_date = DateTimeField(null=True)
    interval = IntegerField(default=0)
    super_admin_id = IntegerField(null=True)

    class Meta:
        database = db

db.connect()
if not db_exists:
    db.create_tables([Admin, Chat, BotData])

# ===========================
# Parser plugins
# ===========================
cfg_parser = config['parser']
logger.info("Loading parser (%s) plugin...", cfg_parser)
parser_config = config['parser-config']
parser_module = importlib.import_module(path_join('plugins', cfg_parser, 'main'))
parser_db_table = parser_module.db_table
logger.info("initlizing parser database...")
parser_module.db_proxy.initialize(db)
parser_module.db_proxy.connect()
if not db.table_exists(parser_db_table):
    parser_module.db_proxy.create_tables([parser_db_table])
logger.info("initlizing parser...")
parser = parser_module.Parser(parser_config)

# ===========================
# Telegram Post Bot
# https://github.com/bsimjoo/telegram-post-bot
# ===========================
if 'proxy-url' in config:
    updater = Updater(token=config['token'], use_context=True, request_kwargs={'proxy_url': config['proxy-url']})
else:
    updater = Updater(token=config.get('telegram-token'), use_context=True)

decorators = HandlersDecorator(updater.dispatcher)

def admins_list():
    return [admin.id for admin in Admin.select()]

@decorators.CommandHandler
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat = update.message.chat
    
    if chat.type == 'private' and len(context.args) > 0:
        if context.args[0] == config['token']:
            Admin.create(id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name, language=user.language_code, state=0, privilege=1)
            update.message.reply_text("You are now a super admin.")
        #TODO: add admins registration
    
    q = Chat.select().where(Chat.id == chat.id)
    if q.exists():
        update.message.reply_text("You are already registered.")        #TODO: configurable messages
        return
    
    update.message.reply_text("You are now registered.")
    members_count = chat.get_member_count()
    Chat.create(id=chat.id, type=chat.type, title=chat.title, username=chat.username, first_name=chat.first_name, last_name=chat.last_name, members_count=members_count-1)  # -1 for bot

@decorators.CommandHandler
@Auth(admins_list)
def members_count(update: Update, context: CallbackContext):
    chats_count = Chat.select().count()
    total_count = sum(chat.members_count for chat in Chat.select())
    update.message.reply_text("There are {} chats and {} members in total.".format(chats_count, total_count))

#TODO: remove this test message handler
@decorators.MessageHandler()
def echo(update: Update, context: CallbackContext):
    update.message.reply_text(update.message.text)

updater.start_polling()
updater.idle()