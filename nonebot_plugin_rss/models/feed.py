from typing import List, Optional

from pydantic import Field, BaseModel, AnyHttpUrl


class FeedChannel(BaseModel):
    """
    Feed Channel

    https://cyber.harvard.edu/rss/rss.html
    """

    title: str
    link: AnyHttpUrl
    subtitle: str
    language: Optional[str] = None
    generator: Optional[str] = None
    published: Optional[str] = None
    ttl: Optional[int] = None


class FeedEntry(BaseModel):
    """
    Feed Entry

    https://cyber.harvard.edu/rss/rss.html
    """

    title: Optional[str] = None
    link: Optional[AnyHttpUrl] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    published: Optional[str] = None

    image_hash: Optional[str] = None
    """
    图片指纹，用于去重
    """


class FeedParser(BaseModel):
    """
    FeedParserDict Model
    """

    feed: FeedChannel
    entries: List[FeedEntry] = Field(default_factory=list)
