# RSS reader plugin for telegram post bot
from peewee import *
from plugins.parser.model import *

db_proxy = DatabaseProxy()
class RSS_reader_Data(Model):
    last_post_date = DateTimeField(null=True)

    class Meta:
        database = db_proxy
        db_table = 'rss_reader_data'

db_table = RSS_reader_Data

class Parser(ParserModel):
    def __init__(self, config):
        ...

class main:
    
    class db(Model):
        ...

    class Parser(ParserModel):
        def __init__(self, config):
            ...