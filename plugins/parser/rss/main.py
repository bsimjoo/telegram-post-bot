# RSS reader plugin for telegram post bot
from peewee import *
from plugins.parser.model import *
from logging import getLogger

class RSS_reader_Data(Model):
    last_post_date = DateTimeField(null=True)

    class Meta:
        database = DatabaseProxy()
        db_table = 'rss_reader_data'

class Parser(ParserModel):
    def __init__(self, config):
        super().__init__(config, RSS_reader_Data)
        self.logger = getLogger('RSS-reader')

    @property
    def db_table(self):
        return RSS_reader_Data

    def new_posts(self):
        self.logger.info("Getting new posts...")
        ...

    def last_post(self):
        self.logger.info("Getting last post...")
        ...