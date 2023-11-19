import re
import math
import functools
from contextlib import suppress
from typing import Any, Dict, List, Mapping, TypeVar, Optional, Generator

from cachetools.keys import hashkey


def get_cache_headers(
    headers: Optional[Mapping[str, Any]],
) -> Dict[str, Optional[str]]:
    """
    从响应头中获取缓存相关的响应头
    """
    if headers:
        return {
            "Last-Modified": headers.get("Last-Modified") or headers.get("Date"),
            "ETag": headers.get("ETag"),
        }
    return {"Last-Modified": None, "ETag": None}


def convert_size(size: int) -> str:
    """
    将文件大小转换为可读的字符串
    """
    if size == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    size_index = int(math.floor(math.log(size, 1024)))
    value = round(size / math.pow(1024, size_index), 2)
    return f"{value} {size_name[size_index]}"


def cached_async(cache, key=hashkey):
    """
    https://github.com/tkem/cachetools/commit/3f073633ed4f36f05b57838a3e5655e14d3e3524
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            if cache is None:
                return await func(*args, **kwargs)
            else:
                k = key(*args, **kwargs)
                with suppress(KeyError):
                    return cache[k]
                v = await func(*args, **kwargs)
                with suppress(ValueError):
                    cache[k] = v
                return v

        return functools.update_wrapper(wrapper, func)

    return decorator


def regex_validate(regex: str) -> bool:
    """
    正则表达式验证
    """
    try:
        re.compile(regex)
        return True
    except re.error:
        return False


T = TypeVar("T")


def partition_list(data: List[T], size: int) -> Generator[List[T], None, None]:
    """
    将列表按照指定大小分割
    """
    for i in range(0, len(data), size):
        yield data[i : i + size]
