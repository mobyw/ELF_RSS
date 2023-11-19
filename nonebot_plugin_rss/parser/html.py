import re
from html import unescape as html_unescape

import bbcode
from yarl import URL
from pyquery import PyQuery as Pq

from ..config import plugin_config


def handle_bbcode(html: Pq) -> str:
    """
    处理 bbcode
    """
    rss_str = html_unescape(str(html))
    rss_str = re.sub(r"(\[url=[^]]+])?\[img[^]]*].+\[/img](\[/url])?", "", rss_str, flags=re.I)
    # 处理一些 bbcode 标签
    bbcode_tags = [
        "align",
        "b",
        "backcolor",
        "color",
        "font",
        "size",
        "table",
        "tbody",
        "td",
        "tr",
        "u",
        "url",
    ]
    for i in bbcode_tags:
        rss_str = re.sub(rf"\[{i}=[^]]+]", "", rss_str, flags=re.I)
        rss_str = re.sub(rf"\[/?{i}]", "", rss_str, flags=re.I)
    # 去掉结尾被截断的信息
    rss_str = re.sub(r"(\[[^]]+|\[img][^\[\]]+) \.\.\n?</p>", "</p>", rss_str, flags=re.I)
    # 检查正文是否为 bbcode，没有成对的标签也当作不是，从而不进行处理
    bbcode_search = re.search(r"\[/(\w+)]", rss_str)
    if bbcode_search and re.search(f"\\[{bbcode_search[1]}", rss_str):
        parser = bbcode.Parser()
        parser.escape_html = False
        rss_str = parser.format(rss_str)
    return rss_str


def handle_lists(html: Pq, rss_str: str) -> str:
    """
    处理列表
    """
    # 有序/无序列表 标签处理
    for ul in html("ul").items():
        for li in ul("li").items():
            li_str_search = re.search("<li>(.+)</li>", repr(str(li)))
            rss_str = rss_str.replace(str(li), f"\n- {li_str_search[1]}").replace("\\n", "\n")  # type: ignore
    for ol in html("ol").items():
        for index, li in enumerate(ol("li").items()):
            li_str_search = re.search("<li>(.+)</li>", repr(str(li)))
            rss_str = rss_str.replace(str(li), f"\n{index + 1}. {li_str_search[1]}").replace(  # type: ignore
                "\\n", "\n"
            )
    rss_str = re.sub("</(ul|ol)>", "\n", rss_str)
    # 处理没有被 ul / ol 标签包围的 li 标签
    rss_str = rss_str.replace("<li>", "- ").replace("</li>", "")
    return rss_str


def handle_links(html: Pq, rss_str: str) -> str:
    """
    处理链接
    """
    for a in html("a").items():
        a_str = re.search(r"<a [^>]+>.*?</a>", html_unescape(str(a)), flags=re.DOTALL).group()  # type: ignore
        if a.text() and str(a.text()) != a.attr("href"):
            # 去除微博超话
            if re.search(
                r"https://m\.weibo\.cn/p/index\?extparam=\S+&containerid=\w+",
                str(a.attr("href")),
            ):
                rss_str = rss_str.replace(a_str, "")
            # 去除微博话题对应链接 及 微博用户主页链接，只保留文本
            elif (
                str(a.attr("href")).startswith("https://m.weibo.cn/search?containerid=")
                and re.search("#.+#", str(a.text()))
            ) or (str(a.attr("href")).startswith("https://weibo.com/") and str(a.text()).startswith("@")):
                rss_str = rss_str.replace(a_str, str(a.text()))
            else:
                if str(a.attr("href")).startswith("https://weibo.cn/sinaurl?u="):
                    a.attr("href", URL(str(a.attr("href"))).query["u"])
                rss_str = rss_str.replace(a_str, f" {a.text()}: {a.attr('href')}\n")
        else:
            rss_str = rss_str.replace(a_str, f" {a.attr('href')}\n")
    return rss_str


def handle_html(html: Pq) -> str:
    """
    处理 HTML
    """
    rss_str = html_unescape(str(html))
    rss_str = handle_lists(html, rss_str)
    rss_str = handle_links(html, rss_str)
    # 处理一些 HTML 标签
    html_tags = [
        "b",
        "blockquote",
        "code",
        "dd",
        "del",
        "div",
        "dl",
        "dt",
        "em",
        "figure",
        "font",
        "i",
        "iframe",
        "ol",
        "p",
        "pre",
        "s",
        "small",
        "span",
        "strong",
        "sub",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    ]
    # <p> <pre> 标签后增加两个换行
    for i in ["p", "pre"]:
        rss_str = re.sub(f"</{i}>", f"</{i}>\n\n", rss_str)
    # 直接去掉标签，留下内部文本信息
    for i in html_tags:
        rss_str = re.sub(f"<{i} [^>]+>", "", rss_str)
        rss_str = re.sub(f"</?{i}>", "", rss_str)
    rss_str = re.sub(r"<(br|hr)\s?/?>|<(br|hr) [^>]+>", "\n", rss_str)
    rss_str = re.sub(r"<h\d [^>]+>", "\n", rss_str)
    rss_str = re.sub(r"</?h\d>", "\n", rss_str)
    # 删除图片、视频标签
    rss_str = re.sub(r"<video[^>]*>(.*?</video>)?|<img[^>]+>", "", rss_str, flags=re.DOTALL)
    # 去掉多余换行
    while "\n\n\n" in rss_str:
        rss_str = rss_str.replace("\n\n\n", "\n\n")
    rss_str = rss_str.strip()
    if 0 < plugin_config.rss_length_limit < len(rss_str):
        rss_str = f"{rss_str[: plugin_config.rss_length_limit]}..."
    if not rss_str.endswith("\n"):
        rss_str += "\n"
    return rss_str
