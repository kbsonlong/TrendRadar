"""
数据抓取器插件模块
"""
from .base_fetcher import BaseFetcher
from .news_fetcher import NewsNowFetcher

__all__ = ['BaseFetcher', 'NewsNowFetcher']