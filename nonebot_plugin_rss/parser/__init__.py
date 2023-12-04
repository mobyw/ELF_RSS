import re
from io import BytesIO
from typing import List
from difflib import SequenceMatcher

import arrow
import emoji
from nonebot.log import logger
from pyquery import PyQuery as Pq
from nonebot_plugin_saa import Image, MessageFactory

from ..bot import send_rss
from .html import handle_html
from .media import handle_media
from ..config import plugin_config
from .translate import handle_translate
from .parse import ParseBase, ParseState
from .parse import ParseRss as ParseRss
from ..models import Rss, Entry, FeedEntry, EntryCache
from .utils import get_time, check_new, get_summary, check_filter


@ParseBase.append_before_handler()
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    检查是否有新的消息
    """
    logger.trace(f"{rss.name} 开始检查是否有新消息")
    state["new_data"] = await check_new(rss, state["entries"])
    return state


@ParseBase.append_before_handler(priority=11)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    判断是否满足推送条件
    """
    logger.trace(f"{rss.name} 开始判断是否满足推送条件")
    new_data = state["new_data"]
    assert new_data is not None
    for item in new_data.copy():
        summary = get_summary(item)
        # 检查是否包含屏蔽词
        if plugin_config.rss_black_word and re.findall("|".join(plugin_config.rss_black_word), summary):
            logger.info(f"{rss.name} 检测到屏蔽词，跳过消息推送")
            await Entry.add(rss.id, item)
            new_data.remove(item)
            continue
        # 检查是否匹配白名单关键字
        if rss.white_keyword and not (
            re.search(rss.white_keyword, item.title or "") or re.search(rss.white_keyword, summary)
        ):
            await Entry.add(rss.id, item)
            new_data.remove(item)
            continue
        # 检查是否匹配黑名单关键字
        if rss.black_keyword and (
            re.search(rss.black_keyword, item.title or "") or re.search(rss.black_keyword, summary)
        ):
            await Entry.add(rss.id, item)
            new_data.remove(item)
            continue
        # 检查是否只推送有图片的消息
        if (rss.only_pic or rss.contains_pic) and not re.search(r"<img[^>]+>|\[img]", summary):
            logger.info(f"{rss.name} 已开启仅图片/仅含有图片，已跳过无图片消息推送")
            await Entry.add(rss.id, item)
            new_data.remove(item)
            continue
    state["new_data"] = new_data
    return state


@ParseBase.append_before_handler(priority=12)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    对推送列表进行去重过滤
    """
    logger.trace(f"{rss.name} 开始对推送列表进行去重过滤")
    if not rss.filters:
        # 未启用去重
        return state
    new_data = state["new_data"]
    await EntryCache.delete_expired()
    delete: List[int] = []
    for index, item in enumerate(new_data):
        is_duplicate, image_hash = await check_filter(rss, item)
        if is_duplicate:
            await Entry.add(rss.id, item)
            delete.append(index)
        else:
            new_data[index].image_hash = image_hash
    new_data = [item for index, item in enumerate(new_data) if index not in delete]
    state["new_data"] = new_data
    return state


@ParseBase.append_handler(parsing_type="title")
async def _(rss: Rss, state: ParseState, entry: FeedEntry) -> ParseState:
    """
    处理标题
    """
    logger.trace(f"{rss.name} 开始处理标题")
    if rss.only_pic:
        # 如果开启了只推送图片，跳过标题处理
        return state
    title = entry.title or ""
    if not plugin_config.rss_block_quote:
        title = re.sub(r" - 转发 .*", "", title)
    result = f"📰 标题：{title}\n"
    if not rss.only_title:
        # 隔开标题和正文
        result += "\n"
    if rss.translate:
        result += await handle_translate(content=title)
    if rss.only_title:
        # 只推送标题时跳过标题与正文相似度处理
        text = emoji.emojize(result, language="alias")
        if rss.bot_id in plugin_config.rss_hide_url_bots:
            text = text.replace(".", "．")
        state["message"] = text
        logger.debug(f"{rss.name} 只推送标题，跳过标题与正文相似度处理")
        return state
    # 判断标题与正文相似度，避免标题正文一样，或者是标题为正文前缀
    try:
        summary_html = Pq(get_summary(entry))
        similarity = SequenceMatcher(None, summary_html.text()[: len(title)], title)
        # 标题正文相似度
        if similarity.ratio() > 0.6:
            result = ""
    except Exception as e:
        logger.warning(f"{rss.name} 没有正文内容！{e}")
    text = emoji.emojize(result, language="alias")
    if rss.bot_id in plugin_config.rss_hide_url_bots:
        text = text.replace(".", "．")
    state["message"] = text
    return state


@ParseBase.append_handler(parsing_type="summary", priority=1)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    正文处理：仅推送标题、仅推送图片
    """
    logger.trace(f"{rss.name} 开始处理正文，仅推送标题、仅推送图片")
    if rss.only_title or rss.only_pic:
        # 如果开启了只推送标题，跳过正文处理
        state["stop"] = True
    return state


@ParseBase.append_handler(parsing_type="summary")
async def _(rss: Rss, state: ParseState, entry: FeedEntry) -> ParseState:
    """
    正文处理：HTML
    """
    logger.trace(f"{rss.name} 开始处理正文，HTML")
    try:
        # 处理正文并填入 text 字段
        text = handle_html(html=Pq(get_summary(entry)))
        state["text"] = text
    except Exception as e:
        logger.warning(f"{rss.name} 没有正文内容！{e}")
    return state


@ParseBase.append_handler(parsing_type="summary", priority=11)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    正文处理：移除指定内容
    """
    logger.trace(f"{rss.name} 开始处理正文，移除指定内容")
    if rss.contents_to_remove:
        # 移除指定内容
        text = state["text"]
        for pattern in rss.contents_to_remove:
            text = re.sub(pattern, "", text)
        # 去除多余换行
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        text = text.strip()
        text = emoji.emojize(text, language="alias")
        state["text"] = text
    return state


@ParseBase.append_handler(parsing_type="summary", priority=12)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    正文处理：翻译
    """
    logger.trace(f"{rss.name} 开始处理正文，翻译")
    if rss.translate:
        # 翻译
        text = state["text"]
        translation = await handle_translate(text)
        state["text"] = text + "\n" + translation
    return state


@ParseBase.append_handler(parsing_type="summary", priority=13)
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    正文处理：正文文本消息构造
    """
    logger.trace(f"{rss.name} 开始处理正文，正文文本消息构造")
    text = state["text"].strip()
    if rss.bot_id in plugin_config.rss_hide_url_bots:
        text = text.replace(".", "．")
    state["message"] = state["message"] + text if state["message"] else text
    return state


@ParseBase.append_handler(parsing_type="picture")
async def _(rss: Rss, state: ParseState, entry: FeedEntry) -> ParseState:
    """
    图片处理
    """
    logger.trace(f"{rss.name} 开始处理图片")
    if rss.only_title:
        # 只推送标题时跳过图片处理
        return state
    text = ""
    images: List[BytesIO] = []
    try:
        text, images = await handle_media(entry=entry, rss=rss)
    except Exception as e:
        logger.warning(f"{rss.name} 处理图片时出现错误：{e}")
    message = state["message"]
    if text:
        message = (message + text) if message else text
    for image in images:
        message = (message + MessageFactory(Image(image))) if message else MessageFactory(Image(image))
    if message:
        message = message + "\n\n"
    state["message"] = message
    return state


@ParseBase.append_handler(parsing_type="source")
async def _(rss: Rss, state: ParseState, entry: FeedEntry) -> ParseState:
    """
    链接处理
    """
    logger.trace(f"{rss.name} 开始处理链接")
    text = f"🔗 链接：{entry.link}\n" if entry.link else ""
    if rss.bot_id in plugin_config.rss_hide_url_bots:
        text = text.replace(".", "．")
    if text:
        state["message"] = state["message"] + text if state["message"] else text
    return state


@ParseBase.append_handler(parsing_type="date")
async def _(rss: Rss, state: ParseState, entry: FeedEntry) -> ParseState:
    """
    日期处理
    """
    logger.trace(f"{rss.name} 开始处理日期")
    date = get_time(entry)
    date = date.replace(tzinfo="local") if date > arrow.now() else date.to("local")
    text = f"📅 日期：{date.format('YYYY年MM月DD日 HH:mm:ss')}"
    if text:
        state["message"] = state["message"] + text if state["message"] else text
    return state


@ParseBase.append_after_handler()
async def _(rss: Rss, state: ParseState) -> ParseState:
    """
    发送消息并写入缓存
    """
    logger.trace(f"{rss.name} 开始发送消息并写入缓存")
    error_count = 0
    if await send_rss(rss, state["messages"], state["title"]):
        if rss.filters:
            for d in state["new_data"]:
                await EntryCache.add(rss.id, d)
    else:
        error_count += len(state["messages"])
    for d in state["new_data"]:
        await Entry.add(rss.id, d)
    message_count = len(state["new_data"])
    success_count = message_count - error_count
    if message_count > 10 and len(state["messages"]) == 10:
        return state
    if success_count > 0:
        logger.info(f"{rss.name} 新消息推送完毕，共计：{success_count}/{message_count}")
    elif message_count > 0:
        logger.error(f"{rss.name} 新消息推送失败，共计：{message_count}")
    else:
        logger.info(f"{rss.name} 没有新信息")
    return state
