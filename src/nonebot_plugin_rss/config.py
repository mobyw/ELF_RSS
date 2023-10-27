from pathlib import Path
from typing import List, Optional

from nonebot import get_driver
from nonebot_plugin_datastore import get_plugin_data
from pydantic import Extra, Field, BaseModel, AnyHttpUrl


class ELFConfig(BaseModel, extra=Extra.ignore):
    rss_proxy: Optional[str] = None
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
    rss_cache_expire: int = 30
    """
    RSS 去重数据库记录过期时间，单位天
    """
    rss_num_limit: int = 200
    """
    RSS 缓存条目数量限制
    """
    rss_length_limit: int = 1024
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
    rss_image_save_path: Path = Field(
        default=get_plugin_data().data_dir / "images", default_factory=Path
    )
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


config = ELFConfig(**get_driver().config.dict())
