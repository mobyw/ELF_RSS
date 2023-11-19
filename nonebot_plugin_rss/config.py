from pathlib import Path
from typing import List, Optional

from nonebot import get_driver
from nonebot.config import Config
from nonebot_plugin_saa import PlatformTarget
from nonebot_plugin_localstore import get_data_dir
from pydantic import Extra, Field, BaseModel, AnyHttpUrl

data_dir: Path = get_data_dir("nonebot_plugin_rss")


class ELFConfig(BaseModel, extra=Extra.ignore):
    rss_proxy: Optional[AnyHttpUrl] = None
    """
    RSS 插件使用的代理地址
    """
    rss_rsshub: AnyHttpUrl = Field(default="https://rsshub.app")
    """
    RSSHub 地址
    """
    rsshub_backup: List[AnyHttpUrl] = Field(default_factory=list)
    """
    RSSHub 备用地址
    """
    rss_cache_expire: int = 10
    """
    RSS 去重数据库记录过期时间，单位天
    """
    rss_num_limit: int = 200
    """
    RSS 缓存条目数量限制
    """
    rss_length_limit: int = 256
    """
    RSS 正文长度限制
    """
    rss_image_size_limit: int = 2048
    """
    RSS 图片尺寸限制
    """
    rss_gif_zip_threshold: int = 6 * 1024
    """
    RSS GIF 压缩阈值，单位 KB
    """
    rss_image_save_name: str = "{subs}/{name}{ext}"
    """
    RSS 图片保存名称
    """
    rss_image_save_path: Path = Field(default=data_dir / "images")
    """
    RSS 图片保存路径
    """
    rss_block_quote: bool = True
    """
    RSS 是否屏蔽转发
    """
    rss_black_word: List[str] = Field(default_factory=list)
    """
    RSS 屏蔽关键词，支持正则表达式
    """
    rss_language_detection_key: Optional[str] = None
    """
    RSS 语言检测 API Key
    前往 https://detectlanguage.com/documentation 获取
    """
    rss_translate_deepl_key: Optional[str] = None
    """
    RSS 使用的 DeepL 翻译 API Key
    """
    rss_translate_baidu_id: Optional[str] = None
    """
    RSS 使用的百度翻译 API AppID
    """
    rss_translate_baidu_key: Optional[str] = None
    """
    RSS 使用的百度翻译 API Key
    """
    rss_admin_bot_id: Optional[str] = None
    """
    RSS 发送管理员通知的 Bot ID
    """
    rss_admin_targets: List[PlatformTarget] = Field(default_factory=list)
    """
    RSS 发送管理员通知的目标
    """
    rss_hide_url_bots: List[str] = Field(default_factory=list)
    """
    RSS 替换链接的 Bot ID 列表
    """


plugin_config = ELFConfig(**get_driver().config.dict())
nonebot_config = Config(**get_driver().config.dict())
