# RSS reader plugin for telegram post bot
from numpy import iterable
from peewee import *
from plugins.parser.model import *
from logging import getLogger
import feedparser
from bs4 import BeautifulSoup
from telegram import ParseMode

class RSS_reader_Data(Model):
    last_post_date = DateTimeField(null=True)
    source = CharField() # this will use to check if source changed or not

    class Meta:
        database = DatabaseProxy()
        db_table = 'rss_reader_data'

class Parser(ParserModel):
    def __init__(self, config):
        self.config = config
        self.logger = getLogger('RSS-reader')
        self.logger.info('Initializing RSS reader plugin...')
        self.properties = RSS_reader_Data.get_or_create()
        if self.properties.source != self.config['source']:
            self.logger.info('Source changed, updating...')
            self.properties.source = self.config['source']
            self.properties.last_post_date = None
            self.properties.save()

    @property
    def db_table(self):
        return RSS_reader_Data

    def new_posts(self) -> iterable[Message]:
        self.logger.info("Getting new posts...")
        feeds = feedparser.parse(self.properties.source)
        if feeds.bozo == 1:
            self.logger.error("Error: %s", feeds.bozo_exception)
            return
        if feeds.status != 200:
            self.logger.error("Error: %s", feeds.status)
            return
        if not iterable(feeds.entries):
            self.logger.error("Error: No entries found")
            return
        for entry in feeds.entries:
            if self.properties.last_post_date is None:
                self.properties.last_post_date = entry.published_parsed
                self.properties.save()
            elif entry.published_parsed > self.properties.last_post_date:
                self.properties.last_post_date = entry.published_parsed
                self.properties.save()
                yield self.render_post(entry)

    SAFE_TAGS_ATTRS = {
        'a': ['href'],'b':[],'strong':[],'i':[],'em':[],'code':[],'s':[],'strike':[],'del':[],'u':[],'pre':['language'],'img':['src'],'video':['src'],'source':['src']
    }

    def render_post(self, post) -> iterable[Message]:
        messages = []
        first = True
        for content in post.content:
            if content.type == 'text/html':
                body = self.purge_html(content.value)
                medias = []
                medias = body.find_all('img')+body.find_all('video')
                if medias:
                    before, after = None, str(body)

                    for media in medias:
                        split_by = str(media)
                        link = None
                        if media.parent.name == 'a':
                            split_by = str(media.parent)
                            link = media.parent['href']
                        before,after = after.split(split_by,1)
                        if before:
                            if first:
                                messages.append(TextMessage(before,ParseMode.HTML))
                                first = False
                            else:
                                messages[-1].text = before
                        if link:
                            messages.append(PhotoMessage(media['src'], parse_mode=ParseMode.HTML, inline_keyboard=[[InlineKeyboardButton('Open image link',url=link)]]))
                        else:
                            messages.append(PhotoMessage(media['src'], parse_mode=ParseMode.HTML))

    def purge_html(self, html):
        """
        Remove all unsupported tags and attributes from html
        """

        soup = BeautifulSoup(html, 'html.parser')
        self.logger.debug('purging html...')
        return BeautifulSoup(''.join(self.__purge_tag_rec(soup.contents)), 'html.parser')

    def __purge_tag_rec(self, children):
        self.logger.debug('children: %s',repr(children))
        for tag in children:
            self.logger.debug('checking tag: %s',repr(tag))
            if getattr(tag, 'contents', None) is not None:
                self.__purge_tag_rec(tag.contents)
                if not tag.name in self.SAFE_TAGS_ATTRS:
                    self.logger.debug('replacing tag %s with %s',repr(tag),''.join(map(str,tag.contents)))
                    tag.replace_with(''.join(map(str,tag.contents)))
                else:
                    self.logger.debug('tag %s is safe',tag.name)
                    for attr in tag.attrs:
                        if attr not in self.SAFE_TAGS_ATTRS[tag.name]:
                            self.logger.debug('removing attribute %s from tag %s',attr,tag.name)
                            del tag[attr]
            else:
                self.logger.debug('not changing: %s',tag.string)
        return children

    def summarize(self):
        ...

    def last_post(self):
        self.logger.info("Getting last post...")
        ...