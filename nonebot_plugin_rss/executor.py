from datetime import datetime
from typing import Any, Dict, Tuple, Optional

import feedparser
from yarl import URL
from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot_plugin_saa import Text
from nonebot.drivers import Driver, Request, HTTPClientMixin

from . import trigger
from .parser import ParseRss
from .config import plugin_config
from .utils import get_cache_headers
from .models import Rss, Entry, FeedParser
from .bot import send, get_bot, send_to_admin

HEADERS = {
    "Accept": "application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/111.0.0.0 Safari/537.36"
    ),
    "Connection": "keep-alive",
    "Content-Type": "application/xml; charset=utf-8",
}


async def save_first_time_fetch(rss: Rss, model: FeedParser):
    """
    首次抓取缓存保存
    """
    await Entry.clear(rss.id)
    for entry in model.entries:
        await Entry.add(rss.id, entry)
    logger.info(f"{rss.name} 第一次抓取成功！")


async def start(rss: Rss):
    """
    RSS 检查更新入口
    """
    bot: Optional[Bot] = await get_bot(rss.bot_id)
    if bot is None:
        return
    # 是否首次抓取
    first_time = rss.last_modified is None and rss.etag is None
    model, unmodified = await fetch_rss(rss)
    if unmodified:
        logger.debug(f"{rss.name} 没有新信息")
        return
    if not model:
        # 抓取失败
        rss.error_count += 1
        logger.warning(f"{rss.name} 抓取失败！")
        if first_time:
            if plugin_config.rss_proxy and not rss.proxy:
                rss.proxy = True
                logger.info(f"{rss.name} 第一次抓取失败，自动使用代理抓取")
                await start(rss)
            else:
                await stop_and_notify(rss, bot)
        if rss.error_count >= 100:
            await stop_and_notify(rss, bot)
        return
    if rss.error_count > 0:
        # 重置错误计数
        rss.error_count = 0
    if first_time:
        # 首次抓取处理
        await save_first_time_fetch(rss, model)
        rss.last_modified = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        rss = await rss.update()
        return
    parser = ParseRss(rss)
    await parser.start(model)


async def stop_and_notify(rss: Rss, bot: Bot) -> None:
    """
    停止更新并通知用户
    """
    rss.stop = True
    await rss.update()
    trigger.delete_job(rss)
    if not rss.targets:
        text = f"Bot {bot.self_id} ({bot.adapter.get_name()}) 的 {rss.name}[{rss.get_url()}] 无人订阅！已自动停止更新！"
        logger.info(text)
        await send_to_admin(text)
    else:
        if rss.error_count >= 100:
            text = f"{rss.name}[{rss.get_url()}] 已经连续抓取失败超过 100 次！已自动停止更新！"
            text += "请检查订阅地址{cookies_str}！" if rss.cookie else "请检查订阅地址！"
        else:
            text = f"{rss.name}[{rss.get_url()}] 第一次抓取失败！已自动停止更新！"
            text += "请检查订阅地址{cookies_str}！" if rss.cookie else "请检查订阅地址！"
        logger.info(text)
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            text = text.replace(".", "．")
        await send(bot_id=bot.self_id, targets=rss.get_targets(), message=Text(text))


async def fetch_rss(rss: Rss) -> Tuple[Optional[FeedParser], bool]:
    """
    获取 RSS 并解析为模型
    """
    url = rss.get_url()
    # 本地订阅源不使用代理
    localhost = {"localhost", "127.0.0.1"}
    use_proxy = rss.proxy if URL(url).host not in localhost else None
    proxy = plugin_config.rss_proxy if use_proxy else None
    cookies = rss.cookie or None
    headers = HEADERS.copy()
    unmodified = False
    if not plugin_config.rsshub_backup:
        if rss.etag:
            headers["If-None-Match"] = rss.etag
        if rss.last_modified:
            headers["If-Modified-Since"] = rss.last_modified
    driver: Driver = get_driver()
    assert isinstance(driver, HTTPClientMixin)
    headers.update({"Cookie": cookies}) if cookies else None
    request = Request("GET", url, headers=headers, proxy=proxy, timeout=10)
    try:
        response = await driver.request(request)
        if not plugin_config.rsshub_backup:
            http_caching_headers = get_cache_headers(response.headers)
            rss.etag = http_caching_headers["ETag"]
            rss.last_modified = http_caching_headers["Last-Modified"]
            await rss.update()
        if (
            response.status_code == 200 and int(response.headers.get("Content-Length", "1")) == 0
        ) or response.status_code == 304:
            unmodified = True
            return None, unmodified
        data = feedparser.parse(response.content)
        try:
            model = FeedParser.parse_obj(data)
        except Exception as e:
            logger.debug(f"[{url}] 解析失败！{repr(e)}")
            model = None
    except Exception as e:
        if not URL(rss.url).scheme and plugin_config.rsshub_backup:
            logger.debug(f"[{url}] 访问失败！将使用备用 RSSHub 地址！")
            data = await fetch_rss_backup(rss, driver=driver, proxy=proxy, cookies=cookies, headers=headers)
            try:
                model = FeedParser.parse_obj(data)
            except Exception as ee:
                logger.debug(f"[{url}] 解析失败！{repr(ee)}")
                model = None
        else:
            logger.error(f"[{url}] 访问失败！")
            logger.debug(f"[{url}] {e}")
            model = None
    return model, unmodified


async def fetch_rss_backup(rss: Rss, driver: HTTPClientMixin, proxy, cookies, headers) -> Dict[str, Any]:
    """
    获取备用 RSS 订阅源数据
    """
    data = {}
    for rsshub in plugin_config.rsshub_backup:
        rss_url = rss.get_url(rsshub)
        request = Request("GET", rss_url, cookies=cookies, headers=headers, proxy=proxy, timeout=10)
        try:
            response = await driver.request(request)
            data = feedparser.parse(response.content)
            if data.get("feed"):
                logger.info(f"[{rss_url}] 抓取成功！")
                break
        except Exception:
            logger.debug(f"[{rss_url}] 访问失败！将使用备用 RSSHub 地址！")
            continue
    return data
