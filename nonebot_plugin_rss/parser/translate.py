import re
from typing import Dict, Optional

import emoji
from nonebot.log import logger
from nonebot.utils import run_sync
from deep_translator import BaiduTranslator, DeeplTranslator, GoogleTranslator, single_detection

from ..config import plugin_config


@run_sync
def baidu_translate(text: str, proxies: Optional[Dict[str, str]]) -> str:
    try:
        lang = "auto"
        if plugin_config.rss_language_detection_key:
            lang = single_detection(text, api_key=plugin_config.rss_language_detection_key) or "auto"
        translator = BaiduTranslator(
            source=lang,
            target="zh",
            appid=plugin_config.rss_translate_baidu_id,
            appkey=plugin_config.rss_translate_baidu_key,
            proxies=proxies,
        )
        return f"🌐翻译（Baidu）：\n{translator.translate(re.escape(text))}"
    except Exception as e:
        error_msg = f"Baidu 翻译失败：{e}"
        logger.warning(error_msg)
        raise Exception(error_msg) from e


@run_sync
def deepl_translate(text: str, proxies: Optional[Dict[str, str]]) -> str:
    try:
        lang = "auto"
        if plugin_config.rss_language_detection_key:
            lang = single_detection(text, api_key=plugin_config.rss_language_detection_key) or "auto"
        translator = DeeplTranslator(
            api_key=plugin_config.rss_translate_deepl_key,
            source=lang,
            target="zh",
            use_free_api=True,
            proxies=proxies,
        )
        return f"🌐翻译（DeepL）：\n{translator.translate(re.escape(text))}"
    except Exception as e:
        error_msg = f"DeepL 翻译失败：{e}"
        logger.warning(error_msg)
        raise Exception(error_msg) from e


@run_sync
def google_translate(text: str, proxies: Optional[Dict[str, str]]) -> str:
    try:
        translator = GoogleTranslator(source="auto", target="zh-CN", proxies=proxies)
        return f"🌐翻译（Google）：\n{translator.translate(re.escape(text))}"
    except Exception as e:
        error_msg = f"Google 翻译失败：{e}"
        logger.warning(error_msg)
        raise Exception(error_msg) from e


async def handle_translate(content: str) -> str:
    """
    翻译处理
    """
    proxies = (
        {
            "https": f"{plugin_config.rss_proxy.host}:{plugin_config.rss_proxy.port}",
            "http": f"{plugin_config.rss_proxy.host}:{plugin_config.rss_proxy.port}",
        }
        if plugin_config.rss_proxy
        else None
    )
    text = emoji.demojize(content)
    text = re.sub(r":[A-Za-z_]*:", " ", text)
    try:
        # 优先级： DeepL > 百度 > Google
        # 异常时使用 Google 重试
        retry_flag = False
        try:
            if plugin_config.rss_translate_deepl_key:
                text = await deepl_translate(text=text, proxies=proxies)
            elif plugin_config.rss_translate_baidu_id and plugin_config.rss_translate_baidu_key:
                text = await baidu_translate(content, proxies=proxies)
            else:
                retry_flag = True
        except Exception:
            retry_flag = True
        if retry_flag:
            text = await google_translate(text=text, proxies=proxies)
    except Exception as e:
        logger.error(f"翻译失败：{e}")
        text = str(e)
    text = text.replace("\\", "")
    return text
