from urllib.parse import quote

import httpx
from nonebot import logger, on_command
from nonebot.typing import T_State
from nonebot.params import CommandArg, State
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.rule import to_me

URL = on_command("短链", rule=to_me(), priority=5)


@URL.handle()
async def handle_first_receive(
    message: Message = CommandArg(), state: T_State = State()
):
    args = str(message).strip()
    if args:
        state["URL"] = args


@URL.got("URL", prompt="输入你想要缩短的链接")
async def handle_url(state: T_State = State()):
    link = str(state["URL"])
    uri = await get_uri_of_url(link)
    await URL.finish(uri)


async def get_uri_of_url(url: str) -> str:
    api = "https://oy.mk/api/insert"
    async with httpx.AsyncClient(proxies={}) as client:
        try:
            url = quote(url, "utf-8")
            res = await client.get(f"{api}?url={url}")
            res = res.json()
            if res["code"] != 200:
                raise httpx.HTTPStatusError
            return res["data"]["url"]
        except httpx.HTTPStatusError as e:
            msg = f"获取短链出错：{e}"
            logger.error(msg)
            return msg
