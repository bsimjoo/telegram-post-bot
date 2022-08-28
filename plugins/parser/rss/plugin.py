# RSS reader plugin for telegram post bot
from peewee import *
from plugins.parser.model import *
from logging import getLogger
import feedparser, requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup as Soup
from telegram import ParseMode
from time import mktime, sleep,struct_time
from datetime import datetime

def convert_date(struct:struct_time):
        return datetime.fromtimestamp(mktime(struct))

db_proxy = DatabaseProxy()
class RSS_reader_Data(Model):
    last_post_date = DateTimeField(null=True)
    source = CharField(null=True) # this will use to check if source changed or not

    class Meta:
        database = db_proxy
        db_table = 'rss_reader_data'

db_table = RSS_reader_Data
class Parser(ParserModel):
    def __init__(self, config):
        super().__init__(config)
        self.logger = getLogger('RSS-reader')
        self.logger.info('Initializing RSS reader plugin...')
        self.properties = RSS_reader_Data.get_or_create(source=self.config['source'])[0]
        if self.config.get('check-host',True):
            self.logger.debug(f"checking hostname change. properties:{urlparse(self.properties.source).hostname} == config:{urlparse(self.config['source']).hostname}")
            if urlparse(self.properties.source).hostname != urlparse(self.config['source']).hostname:
                self.logger.info('Source changed, updating...')
                self.logger.warning('When source changes or bot runs for the first time it just saves the last post date and does not send any post to subscribers.')
                self.properties.source = self.config['source']
                self.properties.last_post_date = None
                self.properties.save()
        else:
            self.logger.debug('check-host skipped')

    def new_posts(self):
        self.logger.info("Getting new posts...")
        req = requests.get(self.properties.source)
        feeds = feedparser.parse(req.content)
        if req.status_code != 200:
            self.logger.error("Error: %d", req.status_code)
            return
        if feeds.bozo == 1:
            self.logger.error("Error: %s", feeds.bozo_exception)
            return
        if not feeds.entries:
            self.logger.error("Error: No entry found")
            return
        check_date = self.config.get('check-date',True)     # This config is useful for debug

        if self.properties.last_post_date is None and check_date:
            self.properties.last_post_date = convert_date(max([e.published_parsed for e in feeds.entries]))
            self.properties.save()
            if check_date:
                # at default it will return here, but not when check-date is False
                return
        messages = list()
        for entry in feeds.entries:
            if check_date:
                # if check-date is False Always send all posts
                if entry.published_parsed <= self.properties.last_post_date:
                    continue
                self.properties.last_post_date = entry.published_parsed
                self.properties.save()
            messages.extend(self.render_post(entry))
        return messages

    # TAG: ATTRIBUTE(S). attribute could be None | list | str | tuple
    # tag:None -> The tag should not have any attribute (attributes will be omitted)
    # tag:list -> The tag can omit these attribute(s), but other attributes will be omitted
    # tag:str|tuple -> The tag should have this attribute(s) and tags without them will be omitted
    #
    # str is a shortened type for tuples, at next line all str will be converted to tuples ( (attrib,) syntax is so ugly! )

    SAFE_TAGS_ATTRS = {
        'a': 'href','b':None,'strong':None,'i':None,'em':None,'code':None,'s':None,'strike':None,'del':None,'u':None,'pre':['language'],'img':'src','video':'src','source':'src'
    }

    SAFE_TAGS_ATTRS = {x:((y,) if isinstance(y,str) else y) for x,y in SAFE_TAGS_ATTRS.items()} # convert all str attributes to tuples

    def render_post(self, post):
        messages = []
        template = self.config.get('post-template');
        feed = {
            "title":post.title,
            "content":post.description,     # TODO: make it soft coded!
            "link":post.link
        }
        try:
            content = template.format(feed = feed)
        except Exception as e:
            self.logger.error(f"error while trying to format the post: {type(e)}:{str(e)}")
            return []
        if not content:
            return []

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
                        messages.append(TextMessage(str(before),ParseMode.HTML))
                        first = False
                    else:
                        before, broken = self.summarize(Soup(before, 'html.parser'), PhotoMessage.MAX_LENGTH)
                        messages[-1].text = str(before)
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
                messages.append(TextMessage(str(before),ParseMode.HTML))

        if len(messages) > 0:
            last_message = messages[-1]
            if last_message.inline_keyboard is not None:
                last_message.inline_keyboard.append([InlineKeyboardButton('Read more',url=post.link)])
            else:
                last_message.inline_keyboard = [[InlineKeyboardButton('Read more',url=post.link)]]
        
        return messages

    def purge_html(self, html:str):
        """
        Remove all unsupported tags and attributes from html
        """

        soup = Soup(html, 'html.parser')
        self.logger.debug('purging html...')
        poor_html = ''.join(map(str,self.__purge_tag_rec(soup.contents)))
        return Soup(poor_html, 'html.parser')

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
                    attr = self.SAFE_TAGS_ATTRS[tag.name]
                    if attr is None:
                        tag.attrs.clear()
                    elif isinstance(attr, tuple):
                        if all(a in tag.attrs for a in attr):
                            tag.attrs={a:tag[a] for a in attr}
                        else:
                            tag.replace_with(''.join(map(str,tag.contents)))
                    elif isinstance(attr, list):
                        tag.attrs = {a:tag[a] for a in attr if a in tag.attrs}
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
        raise NotImplemented() #TODO: Implement last_post