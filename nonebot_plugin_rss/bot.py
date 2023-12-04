import asyncio
from contextlib import suppress
from typing import Set, List, Union, Optional

import arrow
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot import get_bot as nonebot_get_bot
from nonebot_plugin_saa.registries import Receipt
from nonebot_plugin_saa import Text, MessageFactory, PlatformTarget, MessageSegmentFactory

from .models import Rss
from .config import plugin_config

offline_bots: Set[str] = set()


async def get_bot(bot_id: str) -> Optional[Bot]:
    """
    获取机器人实例
    """
    bot: Optional[Bot] = None
    try:
        bot = nonebot_get_bot(self_id=bot_id)
    except KeyError:
        logger.warning(f"Bot {bot_id} 已离线")
    if bot is None and bot_id not in offline_bots:
        offline_bots.add(bot_id)
        # TODO: send message to admin
    return bot


async def send(
    bot_id: str,
    targets: List[PlatformTarget],
    message: Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory]],
) -> List[Receipt]:
    """
    发送消息到指定目标

    参数:
        bot_id: 机器人 ID
        targets: 目标列表
        message: 消息内容

    返回值:
        List[Receipt]: 消息回执列表
    """
    bot: Optional[Bot] = await get_bot(bot_id)
    if bot is None:
        raise ValueError(f"Bot {bot_id} is offline.")
    if isinstance(message, str):
        message = MessageFactory(Text(message))
    receipts = []
    for target in targets:
        receipt = await message.send_to(target=target, bot=bot)
        receipts.append(receipt)
    return receipts


async def send_to_admin(message: str):
    if not plugin_config.rss_admin_bot_id or not plugin_config.rss_admin_targets:
        return
    await send(
        bot_id=plugin_config.rss_admin_bot_id,
        targets=plugin_config.rss_admin_targets,
        message=Text(message),
    )


async def send_rss(
    rss: Rss,
    messages: List[Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory]]],
    title: Optional[str] = None,
) -> bool:
    """
    RSS 推送
    """
    if not messages:
        # 消息为空
        logger.info("RSS 推送消息为空，跳过推送")
        return False
    bot: Optional[Bot] = await get_bot(rss.bot_id)
    if bot is None:
        # 机器人不在线
        return False
    # 当有多个目标时，只要有一个目标发送成功，就认为发送成功
    flag = any(
        # 多个目标并发发送
        await asyncio.gather(
            *[
                _send_rss_to_target(
                    bot=bot,
                    messages=messages,
                    target=PlatformTarget.deserialize(target),
                    title=title,
                )
                for target in rss.targets
            ]
        )
    )
    return flag


async def _send_rss_to_target(
    bot: Bot,
    messages: List[Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory]]],
    target: PlatformTarget,
    title: Optional[str] = None,
) -> bool:
    """
    发送 RSS 推送消息到指定目标
    """
    flag = False
    start_time = arrow.now()
    # 调用发送消息
    flag = await _send_rss_message(bot, messages, target, title)
    await asyncio.sleep(max(1 - (arrow.now() - start_time).total_seconds(), 0))
    return flag


async def _send_rss_message(
    bot: Bot,
    messages: List[Union[str, MessageSegmentFactory, MessageFactory[MessageSegmentFactory]]],
    target: PlatformTarget,
    title: Optional[str] = None,
) -> bool:
    """
    发送 RSS 推送消息
    """
    if not messages:
        # 消息为空
        logger.info("RSS 推送消息为空，跳过推送")
        return False
    logger.trace(f"发送 RSS 推送消息到 {target.json()}")
    logger.trace(f"消息列表：{[[i.data for i in MessageFactory(m)] for m in messages]}")
    message: MessageFactory
    # 构造单条消息
    if title is not None:
        if bot.self_id in plugin_config.rss_hide_url_bots:
            # 链接特殊处理
            title = title.replace(".", "．")
        message = Text(f"{title}\n\n") + messages[0]
    else:
        message = MessageFactory(messages[0])
    if len(messages) > 1:
        # 构造多条消息
        for m in messages[1:]:
            message += Text("\n" + "-" * 32 + "\n")
            message += MessageFactory(m)
    flag = False
    try:
        # 发送消息
        logger.trace(f"发送消息 {[i.data for i in message]}")
        await message.send_to(target=target, bot=bot)
        flag = True
    except Exception as e:
        # 消息发送失败
        error_msg = f"E: {repr(e)}\n消息发送失败！\n"
        logger.error(error_msg)
        logger.debug(f"Message: {[i.data for i in message]}")
        with suppress(Exception):
            # 发送错误消息
            await MessageFactory(Text(error_msg)).send_to(target=target, bot=bot)
    return flag
