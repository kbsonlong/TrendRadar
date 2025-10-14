"""
新闻抓取器实现
"""
import json
import logging
import re
import os
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from .base_fetcher import BaseFetcher
from src.core.data_models import PlatformConfig
from src.core.utils import clean_title, get_beijing_time

logger = logging.getLogger(__name__)


class NewsFetcher(BaseFetcher):
    """新闻抓取器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.cache_dir = None
        self.debug_mode = False
        self.request_delay = 1  # 默认请求延迟1秒
        self._last_request_time = {}  # 记录每个平台的最后请求时间
        
        # 初始化缓存配置
        if config:
            self.cache_dir = config.get('cache_dir', 'output/cache')
            self.debug_mode = config.get('debug_mode', False)
            self.request_delay = config.get('request_delay', 1)
            
            # 创建缓存目录
            if self.cache_dir:
                Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        return {
            'cache_dir': {
                'type': 'string',
                'required': False,
                'default': 'output/cache',
                'description': '缓存目录路径'
            },
            'debug_mode': {
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': '调试模式，优先使用缓存数据'
            },
            'request_delay': {
                'type': 'number',
                'required': False,
                'default': 1,
                'description': '请求间隔时间（秒）'
            },
            'force_refresh': {
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': '强制刷新，忽略缓存'
            }
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置插件"""
        try:
            # 保存配置
            self.config = config
            self.cache_dir = Path(config.get('cache_dir', 'output/cache'))
            self.debug_mode = config.get('debug_mode', False)
            self.request_delay = config.get('request_delay', 1.0)
            self.force_refresh = config.get('force_refresh', False)
            
            # 创建缓存目录
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            # 如果启用调试模式，调整日志级别
            if self.debug_mode:
                logger.setLevel(logging.DEBUG)
            
            logger.info(f"NewsFetcher 配置完成 - 调试模式: {self.debug_mode}, "
                       f"缓存目录: {self.cache_dir}, 请求延迟: {self.request_delay}s")
            return True
            
        except Exception as e:
            logger.error(f"NewsFetcher 配置失败: {e}")
            return False
    
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
        
        # 检查请求频率限制
        self._check_rate_limit(platform.id)
        
        # 调试模式：优先使用缓存数据
        if self.debug_mode and not getattr(self, 'force_refresh', False):
            cached_data = self._load_cached_data(platform.id)
            if cached_data:
                logger.info(f"使用缓存数据: {platform.name} ({platform.id})")
                return None, cached_data
        
        try:
            # 根据平台类型选择抓取方法
            if platform.type == "news":
                result = self._fetch_news_data(platform, max_retries, timeout)
            elif platform.type == "weibo":
                result = self._fetch_weibo_data(platform, max_retries, timeout)
            elif platform.type == "zhihu":
                result = self._fetch_zhihu_data(platform, max_retries, timeout)
            elif platform.type == "github":
                result = self._fetch_github_data(platform, max_retries, timeout)
            else:
                return f"不支持的平台类型: {platform.type}", {}
            
            # 保存抓取结果到缓存
            error_msg, data = result
            if not error_msg and data:
                self._save_cached_data(platform.id, data)
                
            return result
                
        except Exception as e:
            error_msg = f"抓取数据异常: {str(e)}"
            logger.error(error_msg)
            return error_msg, {}
    
    def _parse_api_weibo_data(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析API返回的微博数据"""
        try:
            titles_data = {}
            
            # 根据API响应结构提取数据 - 新的API格式
            if isinstance(data, dict):
                # 检查是否有items字段
                if 'items' in data and isinstance(data['items'], list):
                    for i, item in enumerate(data['items']):
                        if isinstance(item, dict):
                            title = item.get('title', '')
                            url = item.get('url', '') or item.get('mobileUrl', '')
                            
                            if title:
                                clean_title_text = clean_title(title)
                                titles_data[clean_title_text] = {
                                    'source_name': platform.name,
                                    'ranks': [i + 1],
                                    'time_info': get_beijing_time().isoformat(),
                                    'url': url,
                                    'count': 1,
                                    'hot_value': 0
                                }
                elif 'data' in data:
                    return self._parse_api_weibo_data(data['data'], platform)
                else:
                    # 直接处理字典中的热搜数据
                    for key, value in data.items():
                        if isinstance(value, dict):
                            title = value.get('title', '') or value.get('word', '') or key
                            hot = value.get('hot', 0) or value.get('num', 0)
                            url = value.get('url', '')
                        else:
                            title = str(value)
                            hot = 0
                            url = ''
                        
                        if title:
                            clean_title_text = clean_title(title)
                            titles_data[clean_title_text] = {
                                'source_name': platform.name,
                                'ranks': [],
                                'time_info': get_beijing_time().isoformat(),
                                'url': url,
                                'count': hot or 1,
                                'hot_value': hot
                            }
            
            elif isinstance(data, list):
                # 如果数据是列表格式
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        title = item.get('title', '') or item.get('word', '')
                        hot = item.get('hot', 0)
                        url = item.get('url', '')
                    else:
                        title = str(item)
                        hot = 0
                        url = ''
                    
                    if title:
                        clean_title_text = clean_title(title)
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [i + 1],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': hot or 1,
                            'hot_value': hot
                        }
            
            logger.info(f"API微博数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"API微博数据解析失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _parse_api_zhihu_data(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析API返回的知乎数据"""
        try:
            titles_data = {}
            
            # 解析知乎热搜数据 - 新的API格式
            if isinstance(data, dict):
                # 检查是否有items字段
                if 'items' in data and isinstance(data['items'], list):
                    for i, item in enumerate(data['items']):
                        if isinstance(item, dict):
                            title = item.get('title', '')
                            url = item.get('url', '') or item.get('mobileUrl', '')
                            
                            if title:
                                clean_title_text = clean_title(title)
                                titles_data[clean_title_text] = {
                                    'source_name': platform.name,
                                    'ranks': [i + 1],
                                    'time_info': get_beijing_time().isoformat(),
                                    'url': url,
                                    'count': 1,
                                    'hot_value': 0
                                }
                elif 'data' in data:
                    return self._parse_api_zhihu_data(data['data'], platform)
                else:
                    # 处理字典格式的数据
                    for key, value in data.items():
                        if isinstance(value, dict):
                            title = value.get('title', '') or value.get('question', '') or value.get('name', '') or key
                            hot = value.get('hot', 0) or value.get('heat', 0)
                            url = value.get('url', '') or value.get('link', '')
                        else:
                            title = str(value)
                            hot = 0
                            url = ''
                        
                        if title:
                            clean_title_text = clean_title(title)
                            titles_data[clean_title_text] = {
                                'source_name': platform.name,
                                'ranks': [],
                                'time_info': get_beijing_time().isoformat(),
                                'url': url,
                                'count': hot or 1,
                                'hot_value': hot
                            }
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        title = item.get('title', '') or item.get('question', '') or item.get('name', '')
                        hot = item.get('hot', 0) or item.get('heat', 0)
                        url = item.get('url', '') or item.get('link', '')
                    else:
                        title = str(item)
                        hot = 0
                        url = ''
                    
                    if title and len(title.strip()) > 0:
                        clean_title_text = clean_title(title)
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [i + 1],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': hot or 1,
                            'hot_value': hot
                        }
            
            logger.info(f"API知乎数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"API知乎数据解析失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _parse_api_coolapk_data(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析API返回的酷安数据"""
        try:
            titles_data = {}
            
            # 解析酷安热搜数据 - 新的API格式
            if isinstance(data, dict):
                # 检查是否有items字段
                if 'items' in data and isinstance(data['items'], list):
                    for i, item in enumerate(data['items']):
                        if isinstance(item, dict):
                            title = item.get('title', '')
                            url = item.get('url', '') or item.get('mobileUrl', '')
                            
                            if title:
                                clean_title_text = clean_title(title)
                                titles_data[clean_title_text] = {
                                    'source_name': platform.name,
                                    'ranks': [i + 1],
                                    'time_info': get_beijing_time().isoformat(),
                                    'url': url,
                                    'count': 1,
                                    'hot_value': 0
                                }
                elif 'data' in data:
                    return self._parse_api_coolapk_data(data['data'], platform)
                else:
                    # 处理字典格式的数据
                    for key, value in data.items():
                        if isinstance(value, dict):
                            title = value.get('title', '') or value.get('message', '') or key
                            hot = value.get('hot', 0) or value.get('like', 0) or value.get('reply', 0)
                            url = value.get('url', '') or value.get('shareUrl', '')
                        else:
                            title = str(value)
                            hot = 0
                            url = ''
                        
                        if title:
                            clean_title_text = clean_title(title)
                            titles_data[clean_title_text] = {
                                'source_name': platform.name,
                                'ranks': [],
                                'time_info': get_beijing_time().isoformat(),
                                'url': url,
                                'count': hot or 1,
                                'hot_value': hot
                            }
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        title = item.get('title', '') or item.get('message', '') or item.get('name', '')
                        hot = item.get('hot', 0) or item.get('like', 0) or item.get('reply', 0)
                        url = item.get('url', '') or item.get('shareUrl', '')
                    else:
                        title = str(item)
                        hot = 0
                        url = ''
                    
                    if title:
                        clean_title_text = clean_title(title)
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [i + 1],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': hot or 1,
                            'hot_value': hot
                        }
            
            logger.info(f"API酷安数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"API酷安数据解析失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _parse_api_generic_data(self, data: Dict[str, Any], platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析API返回的通用数据"""
        try:
            titles_data = {}
            
            # 通用数据解析
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        title = item.get('title', '') or item.get('name', '') or item.get('text', '') or str(item)
                        hot = item.get('hot', 0) or item.get('count', 0) or item.get('score', 0)
                        url = item.get('url', '') or item.get('link', '')
                    else:
                        title = str(item)
                        hot = 0
                        url = ''
                    
                    if title and len(title.strip()) > 0:
                        clean_title_text = clean_title(title)
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [i + 1],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': hot or 1,
                            'hot_value': hot
                        }
            
            elif isinstance(data, dict):
                if 'data' in data:
                    return self._parse_api_generic_data(data['data'], platform)
                
                # 处理字典数据
                for key, value in data.items():
                    if isinstance(value, dict):
                        title = value.get('title', '') or value.get('name', '') or value.get('text', '') or key
                        hot = value.get('hot', 0) or value.get('count', 0) or value.get('score', 0)
                        url = value.get('url', '') or value.get('link', '')
                    else:
                        title = str(value)
                        hot = 0
                        url = ''
                    
                    if title and len(title.strip()) > 0:
                        clean_title_text = clean_title(title)
                        titles_data[clean_title_text] = {
                            'source_name': platform.name,
                            'ranks': [],
                            'time_info': get_beijing_time().isoformat(),
                            'url': url,
                            'count': hot or 1,
                            'hot_value': hot
                        }
            
            logger.info(f"API通用数据解析完成: {len(titles_data)} 条")
            return None, {platform.id: titles_data}
            
        except Exception as e:
            error_msg = f"API通用数据解析失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _fetch_news_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取新闻数据 - 适配新的API接口"""
        
        # 检查是否为新的API接口格式
        if "newsnow.busiyi.world/api/s" in platform.url:
            return self._fetch_api_data(platform, max_retries, timeout)
        
        # 原有的新闻抓取逻辑
        # 设置请求头
        headers = platform.headers.copy() if platform.headers else {}
        headers.update({
            'Referer': platform.url,
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        logger.info(f"正在请求: {platform.url}")
        logger.debug(f"请求头: {headers}")
        
        # 发送请求
        error_msg, response = self.make_request(
            url=platform.url,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries
        )
        
        if error_msg or not response:
            logger.error(f"请求失败: {error_msg}")
            return error_msg or "请求失败", {}
        
        try:
            # 保存原始响应数据用于调试
            self._save_raw_data(platform.id, response.text, platform.url)
            
            # 解析响应数据
            content = response.text
            logger.info(f"收到响应，内容长度: {len(content)} 字符，状态码: {response.status_code}")
            logger.debug(f"响应头: {dict(response.headers)}")
            
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
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _fetch_weibo_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """获取微博热搜数据 - 支持新的API接口"""
        try:
            logger.info(f"开始抓取微博数据: {platform.name}")
            
            # 检查是否为新的API接口格式
            if "newsnow.busiyi.world/api/s" in platform.url:
                return self._fetch_api_data(platform, max_retries, timeout)
            
            # 调试模式下，如果检测到反爬虫，使用本地测试数据
            if self.debug_mode:
                test_file = Path("test_data/weibo_hot_sample.html")
                if test_file.exists():
                    logger.info("调试模式：使用本地测试数据")
                    with open(test_file, 'r', encoding='utf-8') as f:
                        test_content = f.read()
                    
                    # 解析测试数据
                    parse_error, titles_data = self._parse_weibo_content(test_content, platform)
                    if not parse_error and titles_data:
                        logger.info(f"调试模式：成功解析测试数据 {len(titles_data)} 条")
                        return None, titles_data
                    else:
                        logger.warning(f"调试模式：测试数据解析失败: {parse_error}")
            
            # 检查是否有缓存数据且非强制刷新模式
            if not getattr(self, 'force_refresh', False):
                cached_data = self._load_cached_data(platform.id)
                if cached_data:
                    logger.info(f"使用缓存的微博数据: {len(cached_data)} 条")
                    return None, cached_data
            
            # 获取微博数据
            error_msg, content = self._fetch_news_data(platform, max_retries, timeout)
            if error_msg:
                return error_msg, {}
            
            # 解析微博数据
            parse_error, titles_data = self._parse_weibo_content(content, platform)
            if parse_error:
                return parse_error, titles_data
            
            # 保存解析后的数据
            if titles_data:
                self._save_cached_data(platform.id, titles_data)
            
            return None, titles_data
            
        except Exception as e:
            error_msg = f"微博数据抓取失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _fetch_zhihu_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取知乎数据 - 支持新的API接口"""
        # 检查是否为新的API接口格式
        if "newsnow.busiyi.world/api/s" in platform.url:
            return self._fetch_api_data(platform, max_retries, timeout)
        return self._fetch_news_data(platform, max_retries, timeout)
    
    def _fetch_github_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """抓取 GitHub 数据 - 支持新的API接口"""
        # 检查是否为新的API接口格式
        if "newsnow.busiyi.world/api/s" in platform.url:
            return self._fetch_api_data(platform, max_retries, timeout)
        return self._fetch_news_data(platform, max_retries, timeout)
    
    def _fetch_api_data(
        self,
        platform: PlatformConfig,
        max_retries: int,
        timeout: int
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """使用新的API接口获取数据"""
        try:
            logger.info(f"使用API接口获取数据: {platform.name} - {platform.url}")
            
            # 设置API请求头（基于curl命令）
            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'priority': 'u=1, i',
                'referer': 'https://newsnow.busiyi.world/',
                'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
            }
            
            # 添加Cookie
            if platform.headers and 'cookie' in platform.headers:
                headers['cookie'] = platform.headers['cookie']
            else:
                # 使用默认cookie
                headers['cookie'] = '_ga=GA1.1.1893853238.1760405052; _ga_EL9HHYE5LC=GS2.1.s1760419984$o3$g1$t1760419992$j52$l0$h0'
            
            logger.debug(f"API请求头: {headers}")
            
            # 发送请求
            error_msg, response = self.make_request(
                url=platform.url,
                headers=headers,
                timeout=timeout,
                max_retries=max_retries
            )
            
            if error_msg or not response:
                logger.error(f"API请求失败: {error_msg}")
                return error_msg or "API请求失败", {}
            
            # 保存原始响应数据
            self._save_raw_data(platform.id, response.text, platform.url)
            
            # 解析JSON响应
            try:
                data = response.json()
                logger.info(f"API响应成功，数据格式: {type(data)}")
                logger.debug(f"响应数据预览: {str(data)[:200]}...")
                
                # 根据平台ID解析数据
                if "weibo" in platform.id.lower():
                    return self._parse_api_weibo_data(data, platform)
                elif "zhihu" in platform.id.lower():
                    return self._parse_api_zhihu_data(data, platform)
                elif "coolapk" in platform.id.lower():
                    return self._parse_api_coolapk_data(data, platform)
                else:
                    return self._parse_api_generic_data(data, platform)
                    
            except json.JSONDecodeError as e:
                logger.error(f"API响应JSON解析失败: {e}")
                logger.debug(f"响应内容: {response.text[:200]}...")
                return f"API响应JSON解析失败: {e}", {}
                
        except Exception as e:
            error_msg = f"API接口获取数据失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg, {}
    
    def _parse_weibo_content(self, content: str, platform: PlatformConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """解析微博内容"""
        logger.info(f"开始解析微博内容，内容长度: {len(content)} 字符")
        
        try:
            # 检查是否为访客验证页面
            if "Sina Visitor System" in content or "visitor" in content.lower():
                logger.warning("检测到微博访客验证页面，需要处理反爬虫机制")
                logger.debug(f"访客页面内容片段: {content[:200]}...")
                return "微博访客验证页面，需要处理反爬虫机制", {}
            
            # 尝试解析 JSON
            if content.strip().startswith('{'):
                logger.info("检测到JSON格式，尝试解析JSON数据")
                data = json.loads(content)
                return self._parse_weibo_json(data, platform)
            
            # 正则表达式提取热搜数据
            logger.info("使用正则表达式提取热搜数据")
            hot_pattern = r'<td class="td-01 ranktop">(\d+)</td>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(hot_pattern, content, re.DOTALL)
            
            logger.info(f"正则表达式匹配到 {len(matches)} 条数据")
            
            titles_data = {}
            for rank, href, title in matches:
                clean_title_text = clean_title(title)
                logger.debug(f"处理标题: {title} -> {clean_title_text}")
                
                if clean_title_text:
                    titles_data[clean_title_text] = {
                        'source_name': platform.name,
                        'ranks': [int(rank)],
                        'time_info': get_beijing_time().isoformat(),
                        'url': href,
                        'count': 1
                    }
            
            logger.info(f"微博数据解析完成: {len(titles_data)} 条")
            
            # 如果没有解析到数据，记录调试信息
            if len(titles_data) == 0:
                logger.warning("微博数据解析结果为0条，可能是页面结构变化或反爬虫机制")
                logger.debug(f"页面内容前500字符: {content[:500]}")
                # 检查是否有特定的反爬虫标识
                if "验证" in content or "验证码" in content or "robot" in content.lower():
                    logger.error("检测到反爬虫验证页面")
                    return "微博反爬虫验证页面", {}
                elif len(content) < 1000:
                    logger.error(f"页面内容过短({len(content)}字符)，可能请求被拒绝")
                    return f"微博页面内容过短({len(content)}字符)，可能请求被拒绝", {}
                else:
                    logger.error("页面结构可能已变更，需要更新解析规则")
                    return "微博页面结构可能已变更，需要更新解析规则", {}
            
            return None, {platform.id: titles_data}
            
        except json.JSONDecodeError as e:
            error_msg = f"微博JSON解析失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"解析失败的JSON内容: {content[:200]}")
            return error_msg, {}
        except Exception as e:
            error_msg = f"微博内容解析失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
    
    def _get_cache_file_path(self, platform_id: str, data_type: str = 'parsed') -> str:
        """获取缓存文件路径"""
        if not self.cache_dir:
            return None
            
        date_str = datetime.now().strftime('%Y%m%d')
        cache_subdir = Path(self.cache_dir) / date_str
        cache_subdir.mkdir(parents=True, exist_ok=True)
        
        if data_type == 'raw':
            filename = f"{platform_id}_raw_{date_str}.html"
        else:
            filename = f"{platform_id}_{date_str}.json"
            
        return str(cache_subdir / filename)
    
    def _save_raw_data(self, platform_id: str, content: str, url: str) -> None:
        """保存原始响应数据"""
        if not self.cache_dir:
            return
            
        try:
            cache_file = self._get_cache_file_path(platform_id, 'raw')
            if not cache_file:
                return
                
            raw_data = {
                'platform_id': platform_id,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'content': content,
                'content_length': len(content)
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"原始数据已保存到缓存: {cache_file}")
            
        except Exception as e:
            logger.warning(f"保存原始数据失败: {str(e)}")
    
    def _save_cached_data(self, platform_id: str, data: Dict[str, Any]) -> None:
        """保存解析后的数据到缓存"""
        if not self.cache_dir:
            return
            
        try:
            cache_file = self._get_cache_file_path(platform_id, 'parsed')
            if not cache_file:
                return
                
            cache_data = {
                'platform_id': platform_id,
                'timestamp': datetime.now().isoformat(),
                'data': data,
                'item_count': sum(len(items) for items in data.values())
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"解析数据已保存到缓存: {cache_file}")
            
        except Exception as e:
            logger.warning(f"保存缓存数据失败: {str(e)}")
    
    def _load_cached_data(self, platform_id: str) -> Optional[Dict[str, Any]]:
        """从缓存加载数据"""
        if not self.cache_dir:
            return None
            
        try:
            cache_file = self._get_cache_file_path(platform_id, 'parsed')
            if not cache_file or not os.path.exists(cache_file):
                return None
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # 检查缓存是否过期（默认24小时）
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > timedelta(hours=24):
                logger.info(f"缓存数据已过期: {cache_file}")
                return None
                
            logger.info(f"从缓存加载数据: {cache_file}, 包含 {cache_data.get('item_count', 0)} 条数据")
            return cache_data['data']
            
        except Exception as e:
            logger.warning(f"加载缓存数据失败: {str(e)}")
            return None
    
    def _check_rate_limit(self, platform_id: str) -> None:
        """检查请求频率限制"""
        current_time = time.time()
        last_time = self._last_request_time.get(platform_id, 0)
        
        # 计算需要等待的时间
        wait_time = self.request_delay - (current_time - last_time)
        if wait_time > 0:
            logger.info(f"频率控制：等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)
        
        # 更新最后请求时间
        self._last_request_time[platform_id] = time.time()
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