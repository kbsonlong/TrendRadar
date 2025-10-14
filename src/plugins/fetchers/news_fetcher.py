"""
新闻抓取器实现
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from .base_fetcher import BaseFetcher
from src.core.data_models import PlatformConfig
from src.core.utils import clean_title, get_beijing_time

logger = logging.getLogger(__name__)


class NewsFetcher(BaseFetcher):
    """新闻抓取器"""
    
    def get_name(self) -> str:
        return "NewsFetcher"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def supports_platform(self, platform_type: str) -> bool:
        """支持新闻类平台"""
        return platform_type in ["news", "weibo", "zhihu", "github"]
    
    def fetch_data(
        self,
        platform: PlatformConfig,
        max_retries: int = 2,
        timeout: int = 30
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取新闻数据"""
        logger.info(f"开始抓取新闻数据: {platform.name} ({platform.id})")
        
        try:
            # 根据平台类型选择抓取方法
            if platform.type == "news":
                return self._fetch_news_data(platform, max_retries, timeout)
            elif platform.type == "weibo":
                return self._fetch_weibo_data(platform, max_retries, timeout)
            elif platform.type == "zhihu":
                return self._fetch_zhihu_data(platform, max_retries, timeout)
            elif platform.type == "github":
                return self._fetch_github_data(platform, max_retries, timeout)
            else:
                return f"不支持的平台类型: {platform.type}", {}
                
        except Exception as e:
            error_msg = f"抓取数据异常: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _fetch_news_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取新闻数据"""
        
        # 设置请求头
        headers = platform.headers.copy() if platform.headers else {}
        headers.update({
            'Referer': platform.url,
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # 发送请求
        error_msg, response = self.make_request(
            url=platform.url,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries
        )
        
        if error_msg or not response:
            return error_msg or "请求失败", {}
        
        try:
            # 解析响应数据
            content = response.text
            
            # 根据不同平台解析数据
            if "weibo" in platform.url.lower():
                return self._parse_weibo_content(content, platform)
            elif "zhihu" in platform.url.lower():
                return self._parse_zhihu_content(content, platform)
            elif "github" in platform.url.lower():
                return self._parse_github_content(content, platform)
            else:
                return self._parse_generic_news(content, platform)
                
        except Exception as e:
            error_msg = f"解析数据失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _fetch_weibo_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取微博数据"""
        return self._fetch_news_data(platform, max_retries, timeout)
    
    def _fetch_zhihu_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取知乎数据"""
        return self._fetch_news_data(platform, max_retries, timeout)
    
    def _fetch_github_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取 GitHub 数据"""
        return self._fetch_news_data(platform, max_retries, timeout)
    
    def _parse_weibo_content(self, content: str, platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析微博内容"""
        try:
            # 尝试解析 JSON
            if content.strip().startswith('{'):
                data = json.loads(content)
                return self._parse_weibo_json(data, platform)
            
            # 正则表达式提取热搜数据
            hot_pattern = r'<td class="td-01 ranktop">(\d+)</td>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(hot_pattern, content, re.DOTALL)
            
            titles_data = {}
            for rank, href, title in matches:
                clean_title_text = clean_title(title)
                if clean_title_text:
                    titles_data[clean_title_text] = {
                        'source_name': platform.name,
                        'ranks': [int(rank)],
                        'time_info': get_beijing_time().isoformat(),
                        'url': href,
                        'count': 1
                    }
            
            logger.info(f"微博数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"微博内容解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_weibo_json(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析微博 JSON 数据"""
        try:
            titles_data = {}
            
            # 根据微博数据结构提取热搜
            if 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    if 'word' in item:
                        title = clean_title(item['word'])
                        rank = item.get('num', 0)
                        href = item.get('url', '')
                        
                        titles_data[title] = {
                            'source_name': platform.name,
                            'ranks': [rank] if rank else [],
                            'time_info': get_beijing_time().isoformat(),
                            'url': href,
                            'count': 1
                        }
            
            logger.info(f"微博 JSON 数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"微博 JSON 解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_zhihu_content(self, content: str, platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析知乎内容"""
        try:
            # 尝试解析 JSON
            if content.strip().startswith('{'):
                data = json.loads(content)
                return self._parse_zhihu_json(data, platform)
            
            # 正则表达式提取热搜数据
            hot_pattern = r'<div[^>]*class="[^"]*HotList-item[^"]*"[^>]*>.*?<div[^>]*class="[^"]*HotList-itemTitle[^"]*"[^>]*>([^<]+)</div>'
            matches = re.findall(hot_pattern, content, re.DOTALL)
            
            titles_data = {}
            for i, title in enumerate(matches):
                clean_title_text = clean_title(title)
                if clean_title_text:
                    titles_data[clean_title_text] = {
                        'source_name': platform.name,
                        'ranks': [i + 1],
                        'time_info': get_beijing_time().isoformat(),
                        'url': '',
                        'count': 1
                    }
            
            logger.info(f"知乎数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"知乎内容解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_zhihu_json(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析知乎 JSON 数据"""
        try:
            titles_data = {}
            
            # 根据知乎数据结构提取热搜
            if 'data' in data:
                hot_list = data['data']
                if isinstance(hot_list, list):
                    for i, item in enumerate(hot_list):
                        if 'target' in item and 'title' in item['target']:
                            title = clean_title(item['target']['title'])
                            url = item['target'].get('url', '')
                            
                            titles_data[title] = {
                                'source_name': platform.name,
                                'ranks': [i + 1],
                                'time_info': get_beijing_time().isoformat(),
                                'url': url,
                                'count': 1
                            }
            
            logger.info(f"知乎 JSON 数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"知乎 JSON 解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_github_content(self, content: str, platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析 GitHub 内容"""
        try:
            # 尝试解析 JSON
            if content.strip().startswith('{'):
                data = json.loads(content)
                return self._parse_github_json(data, platform)
            
            # GitHub 通常是 JSON 格式
            return "GitHub 数据格式不支持", {}
            
        except Exception as e:
            error_msg = f"GitHub 内容解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_github_json(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析 GitHub JSON 数据"""
        try:
            titles_data = {}
            
            # 根据 GitHub 数据结构提取趋势
            if isinstance(data, list):
                for i, repo in enumerate(data):
                    if 'name' in repo:
                        title = clean_title(repo['name'])
                        description = repo.get('description', '')
                        full_title = f"{title} - {description}" if description else title
                        url = repo.get('html_url', '')
                        
                        titles_data[full_title] = {
                            'source_name': platform.name,
                            'ranks': [i + 1],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': 1
                        }
            
            logger.info(f"GitHub JSON 数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"GitHub JSON 解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_generic_news(self, content: str, platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析通用新闻内容"""
        try:
            titles_data = {}
            
            # 通用标题提取模式
            title_patterns = [
                r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>',  # 链接标题
                r'<h[1-6][^>]*>([^<]+)</h[1-6]>',  # 标题标签
                r'<div[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</div>',  # div标题
                r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>',  # span标题
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    if isinstance(match, tuple):
                        if len(match) == 2:  # 链接模式
                            href, title = match
                        else:
                            continue
                    else:
                        href = ''
                        title = match
                    
                    clean_title_text = clean_title(title)
                    if clean_title_text and len(clean_title_text) > 5:  # 过滤短标题
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [],
                            'time_info': get_beijing_time().isoformat(),
                            'url': href,
                            'count': 1
                        }
            
            logger.info(f"通用新闻数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"通用新闻内容解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}