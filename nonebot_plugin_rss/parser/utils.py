import re
from io import BytesIO
from contextlib import suppress
from typing import List, Tuple, Optional
from email.utils import parsedate_to_datetime

import arrow
import imagehash
from nonebot.log import logger
from pyquery import PyQuery as Pq
from PIL import Image, UnidentifiedImageError

from . import media
from ..models import Rss, Entry, FeedEntry, EntryCache


async def check_new(rss: Rss, entries: List[FeedEntry]) -> List[FeedEntry]:
    """
    检查更新的内容
    """
    update: List[FeedEntry] = []
    for entry in entries:
        if not await Entry.check_exist(rss.id, entry):
            update.append(entry)
    update.sort(key=get_time)
    return update


async def check_filter(rss: Rss, item: FeedEntry) -> Tuple[bool, Optional[str]]:
    """
    判断是否去重
    """
    summary = get_summary(item)
    image_hash = None
    is_or: bool = "or" in rss.filters
    link: Optional[str] = item.link if "link" in rss.filters else None
    title: Optional[str] = item.title if "title" in rss.filters else None
    image_hash: Optional[str] = None
    if "image" in rss.filters:
        image_hash = await get_image_hash(rss, summary)
    logger.trace(f"去重检查: {rss.id} {link} {title} {image_hash} {is_or}")
    flag = await EntryCache.check_exist(rss.id, link, title, image_hash, is_or)
    return flag, image_hash


async def get_image_hash(rss: Rss, summary: str) -> Optional[str]:
    """
    获取图片的指纹
    """
    try:
        summary_doc = Pq(summary)
    except Exception as e:
        logger.warning(e)
        # 没有正文内容直接跳过
        return None
    img_doc = summary_doc("img")
    # 只处理仅有一张图片的情况
    if len(img_doc) != 1:
        return None
    url = img_doc.attr("src")
    if not url:
        return None
    # 通过图像的指纹来判断是否实际是同一张图片
    content = await media.download_image(str(url), rss.proxy)
    if not content:
        return None
    try:
        im = Image.open(BytesIO(content))
    except UnidentifiedImageError:
        return None
    # GIF 图片的 image_hash 实际上是第一帧的值，为了避免误伤直接跳过
    if im.format == "GIF":
        return None
    return str(imagehash.dhash(im))


def get_summary(entry: FeedEntry) -> str:
    """
    获取正文
    """
    summary: str = entry.summary or ""
    return f"<div>{summary}</div>" if re.search("^https?://", summary) else summary


def get_author(entry: FeedEntry) -> str:
    """
    获取作者
    """
    return entry.author or ""


def get_time(entry: FeedEntry) -> arrow.Arrow:
    """
    获取条目的时间
    """
    if date := entry.published:
        with suppress(Exception):
            date = parsedate_to_datetime(date)
        return arrow.get(date)
    return arrow.now()
