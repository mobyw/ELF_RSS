import re
import random
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Union, Optional

from yarl import URL
from nonebot import get_driver
from nonebot.log import logger
from pyquery import PyQuery as Pq
from PIL import Image, UnidentifiedImageError
from nonebot.drivers import Driver, Request, HTTPClientMixin
from tenacity import RetryError, retry, stop_after_delay, stop_after_attempt

from . import utils
from ..config import plugin_config
from ..models import Rss, FeedEntry


@retry(stop=(stop_after_attempt(5) | stop_after_delay(30)))
async def resize_gif(url: str, resize_ratio: int = 2) -> Optional[bytes]:
    """
    通过 ezgif 压缩 GIF
    """
    driver: Driver = get_driver()
    assert isinstance(driver, HTTPClientMixin)
    request = Request("POST", "https://s3.ezgif.com/resize", data={"new-image-url": url}, timeout=10)
    response = await driver.request(request)
    data = Pq(response.content)
    next_url = data("form").attr("action")
    _file = data("form > input[type=hidden]:nth-child(1)").attr("value")
    token = data("form > input[type=hidden]:nth-child(2)").attr("value")
    old_width = data("form > input[type=hidden]:nth-child(3)").attr("value")
    old_height = data("form > input[type=hidden]:nth-child(4)").attr("value")
    next_data = {
        "file": _file,
        "token": token,
        "old_width": old_width,
        "old_height": old_height,
        "width": str(int(str(old_width)) // resize_ratio),
        "method": "gifsicle",
        "ar": "force",
    }
    request = Request("POST", str(next_url), params="ajax=true", data=next_data, timeout=10)
    response = await driver.request(request)
    data = Pq(response.content)
    output_img_url = "https:" + str(data("img:nth-child(1)").attr("src"))
    return await download_image(output_img_url)


async def zip_pic(url: str, content: bytes) -> Union[Image.Image, bytes, None]:
    """
    图片压缩
    """
    try:
        im = Image.open(BytesIO(content))
    except UnidentifiedImageError:
        logger.error(f"无法识别图像文件 链接：[{url}]")
        return None
    if im.format != "GIF":
        # 先把 WEBP 图像转为 PNG
        if im.format == "WEBP":
            with BytesIO() as output:
                im.save(output, "PNG")
                im = Image.open(output)
        # 对图像文件进行缩小处理
        im.thumbnail((plugin_config.rss_image_size_limit, plugin_config.rss_image_size_limit))
        width, height = im.size
        logger.debug(f"Resize image to: {width} x {height}")
        # 和谐
        points = [(0, 0), (0, height - 1), (width - 1, 0), (width - 1, height - 1)]
        for x, y in points:
            im.putpixel((x, y), random.randint(0, 255))
        return im
    else:
        if len(content) > plugin_config.rss_gif_zip_threshold * 1024:
            try:
                return await resize_gif(url)
            except RetryError:
                logger.warning(f"GIF 图片[{url}]压缩失败，将发送原图")
        return content


def image_bytesio(content: Union[Image.Image, bytes, None]) -> Optional[BytesIO]:
    if not content:
        return None
    if isinstance(content, Image.Image):
        output = BytesIO()
        content.save(output, format=content.format)
        return output
    if isinstance(content, bytes):
        return BytesIO(content)
    return None


@retry(stop=(stop_after_attempt(5) | stop_after_delay(30)))
async def _download_image(url: str, proxy: bool) -> Optional[bytes]:
    """
    下载图片
    """
    referer = f"{URL(url).scheme}://{URL(url).host}/"
    headers = {"referer": referer}
    driver: Driver = get_driver()
    assert isinstance(driver, HTTPClientMixin)
    request = Request(
        "GET",
        url,
        headers=headers,
        proxy=plugin_config.rss_proxy if proxy else None,
        timeout=10,
    )
    try:
        response = await driver.request(request)
        # 如果图片无法获取到，直接返回
        if not response.content:
            logger.error(f"图片[{url}]下载失败！{response.status_code}")
            return None
        # 如果图片格式为 SVG ，先转换为 PNG
        if response.headers["Content-Type"].startswith("image/svg+xml"):
            next_url = str(URL("https://images.weserv.nl/").with_query(f"url={url}&output=png"))
            return await download_image(next_url, proxy)
        if not isinstance(response.content, bytes):
            return None
        return response.content
    except Exception as e:
        logger.warning(f"图片[{url}]下载失败！将重试最多 5 次！\n{e}")
        raise


async def download_image(url: str, proxy: bool = False) -> Optional[bytes]:
    """
    下载图片
    """
    try:
        return await _download_image(url=url, proxy=proxy)
    except RetryError:
        logger.error(f"图片[{url}]下载失败！已达最大重试次数！有可能需要开启代理！")
        return None


async def handle_image(url: str, img_proxy: bool, rss: Optional[Rss] = None) -> Optional[BytesIO]:
    """
    处理图片
    """
    # TODO: 处理图片
    if content := await download_image(url, img_proxy):
        if rss is not None and rss.download_pic:
            _url = URL(url)
            logger.debug(f"正在保存图片: {url}")
            try:
                save_image(content=content, file_url=_url, rss=rss)
            except Exception as e:
                logger.warning(f"在保存图片到本地时出现错误\nE:{repr(e)}")
        if resize_content := await zip_pic(url, content):
            if bytesio := image_bytesio(resize_content):
                return bytesio
    return None


async def handle_media(entry: FeedEntry, proxy: bool, max_num: int) -> Tuple[str, List[BytesIO]]:
    """
    处理媒体文件
    """
    if max_num == 0:
        # 不发送图片
        return "", []
    html = Pq(utils.get_summary(entry))
    message = ""
    images: List[BytesIO] = []
    # 处理图片
    doc_img = list(html("img").items())
    # 只发送限定数量的图片，防止刷屏
    if 0 < max_num < len(doc_img):
        message += f"\n因启用图片数量限制，只展示 {max_num} 张图片："
        doc_img = doc_img[:max_num]
    for img in doc_img:
        url = img.attr("src")
        image = await handle_image(str(url), proxy) if url else None
        images.append(image) if image else None
    # 处理视频
    if doc_video := html("video"):
        for video in doc_video.items():
            url = video.attr("poster")
            image = await handle_image(str(url), proxy) if url else None
            images.append(image) if image else None
    return message, images


async def handle_bbcode_img(html: Pq, proxy: bool, num: int) -> Tuple[str, List[BytesIO]]:
    """
    处理 bbcode 图片
    """
    message = ""
    images: List[BytesIO] = []
    sources = re.findall(r"\[img[^]]*](.+)\[/img]", str(html), flags=re.I)
    # 只发送限定数量的图片，防止刷屏
    if 0 < num < len(sources):
        message = f"\n因启用图片数量限制，目前只有 {num} 张图片："
        sources = sources[:num]
    for source in sources:
        image = await handle_image(source, proxy)
        images.append(image) if image else None
    return message, images


def filename_format(file_url: URL, rss: Rss) -> Path:
    """
    根据规则格式化文件名
    """
    format_rule = plugin_config.rss_image_save_name
    save_path = plugin_config.rss_image_save_path
    rules = {  # 替换格式化字符串
        "{subs}": rss.name,
        "{name}": file_url.name if "{ext}" not in format_rule else Path(file_url.name).stem,
        "{ext}": file_url.suffix if "{ext}" in format_rule else "",
    }
    for k, v in rules.items():
        format_rule = format_rule.replace(k, v)
    return save_path / format_rule


def save_image(content: bytes, file_url: URL, rss: Rss) -> None:
    """
    保存原图到本地
    """
    save_path = filename_format(file_url=file_url, rss=rss)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)
