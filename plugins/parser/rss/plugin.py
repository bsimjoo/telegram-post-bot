# RSS reader plugin for telegram post bot
from numpy import iterable
from peewee import *
from plugins.parser.model import *
from logging import getLogger
import feedparser
from bs4 import BeautifulSoup as Soup
from telegram import ParseMode
import requests

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
        contents = [c for c in post.content if c.type == 'text/html'] or [c for c in post.content if c.type == 'text/plain']
        if not contents:
            return []
        content = contents[0].value

        body = self.purge_html(content)
        medias = list(body('img'))+list(body('video'))
        first = True
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
                        before, broken = self.summarize(Soup(before, 'html.parser'), TextMessage.MAX_LENGTH)
                        messages.append(TextMessage(before,ParseMode.HTML))
                        first = False
                    else:
                        before, broken = self.summarize(Soup(before, 'html.parser'), PhotoMessage.MAX_LENGTH)
                        messages[-1].text = before
                if broken:
                    # if last message is broken and has read more so stop adding more messages
                    break
                if media.name == 'img':
                    self.logger.debug('found image: %s',media['src'])
                    if link:
                        messages.append(PhotoMessage(media['src'], parse_mode=ParseMode.HTML, inline_keyboard=[[InlineKeyboardButton('Open image link',url=link)]]))
                    else:
                        messages.append(PhotoMessage(media['src'], parse_mode=ParseMode.HTML))
                elif media.name == 'video':
                    video_src = ''
                    if 'src' in media.attrs:
                        video_src = media['src']
                    elif getattr(media, 'source', None) is not None:
                        video_src = media.source['src']
                    headers=requests.head(video_src).headers
                    downloadable = 'attachment' in headers.get('Content-Disposition', '')
                    self.logger.debug('found %s video: %s', 'downloadable' if downloadable else 'not downloadable', video_src)
                    if not downloadable:
                        messages.append(TextMessage('Video is not downloadable'), parse_mode=ParseMode.HTML, inline_keyboard=[[InlineKeyboardButton('Open video link',url=video_src)]])
                        continue
                    if link:
                        messages.append(VideoMessage(video_src, parse_mode=ParseMode.HTML, inline_keyboard=[[InlineKeyboardButton('Open video link',url=link)]]))
                    else:
                        messages.append(VideoMessage(video_src, parse_mode=ParseMode.HTML))
        else:
            before, broken = self.summarize(body, TextMessage.MAX_LENGTH)
            if before:
                messages.append(TextMessage(before,ParseMode.HTML))

        if len(messages) > 0:
            last_message = messages[-1]
            if last_message.inline_keyboard is not None:
                last_message.inline_keyboard.append([InlineKeyboardButton('Read more',url=post.link)])
            else:
                last_message.inline_keyboard = [[InlineKeyboardButton('Read more',url=post.link)]]

    def purge_html(self, html:str):
        """
        Remove all unsupported tags and attributes from html
        """

        soup = Soup(html, 'html.parser')
        self.logger.debug('purging html...')
        return Soup(''.join(self.__purge_tag_rec(soup.contents)), 'html.parser')

    def __purge_tag_rec(self, children):    #recursive tag purging
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

    def summarize(self, post_content:Soup, max_length = TextMessage.MAX_LENGTH, read_more = '...'):
        trim = len(read_more)
        len_ = len(str(post_content))
        if len_>max_length:
            trim += len_ - max_length
            removed = 0
            for element in reversed(list(post_content.descendants)):
                if (not element.name) and len(str(element))>trim-removed:
                    # if element is text and it's length is greater than trim
                    # then we should break it
                    s = str(element)
                    break_from = s.rfind(' ',0 , trim-removed)
                    element.replace_with(s[:-trim+removed if break_from==-1 else break_from])
                    removed = trim
                else:
                    # if element is not text or it's length is less than trim
                    # then we should remove it
                    element.replace_with('')
                    removed += len(str(element))
                if removed >= trim:
                    break
            post_content.append(read_more)
        return post_content, len_>max_length

    def last_post(self):
        self.logger.info("Getting last post...")
        ...