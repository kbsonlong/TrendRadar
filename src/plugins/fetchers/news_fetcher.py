"""
基于 NewsNow API 的新闻抓取器
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import logging
import requests
from pathlib import Path
import re

from .base_fetcher import BaseFetcher
from src.core.data_models import PlatformConfig, CrawlResult, TitleData
from src.core.utils import get_beijing_time

logger = logging.getLogger(__name__)


class NewsNowFetcher(BaseFetcher):
    """基于 NewsNow API 的统一新闻抓取器"""
    
    # 支持的API平台映射
    PLATFORM_MAPPING = {
        'zhihu': 'zhihu',
        'weibo': 'weibo',
        'weibo_hot': 'weibo',
        'zhihu_hot': 'zhihu',
        'coolapk': 'coolapk',
        'v2ex': 'v2ex',
        'douyin': 'douyin',
        'bilibili': 'bilibili',
        'baidu': 'baidu',
        'tieba': 'tieba',
        'toutiao': 'toutiao',
        'netease': 'netease',
        'sina': 'sina',
        'sohu': 'sohu',
        'qq': 'qq',
        'ifeng': 'ifeng',
        'guancha': 'guancha',
        'thepaper': 'thepaper',
        'jiemian': 'jiemian',
        '36kr': '36kr',
        'pingwest': 'pingwest',
        'huxiu': 'huxiu',
        'solidot': 'solidot',
        'ithome': 'ithome',
        'sspai': 'sspai',
        'segmentfault': 'segmentfault',
        'oschina': 'oschina',
        'csdn': 'csdn',
        'juejin': 'juejin',
        'github': 'github',
        'stackoverflow': 'stackoverflow',
        'reddit': 'reddit',
        'hackernews': 'hackernews',
        'producthunt': 'producthunt',
        'indiehackers': 'indiehackers',
        'v2ex_hot': 'v2ex',
        'zhihu_daily': 'zhihu',
        'weibo_topic': 'weibo',
        'douyin_hot': 'douyin',
        'bilibili_hot': 'bilibili',
    }
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base_url = config.get('api_base_url', 'https://newsnow.busiyi.world/api/s')
        self.debug_mode = config.get('debug_mode', False)
        self.cache_dir = Path(config.get('cache_dir', 'cache/newsnow'))
        self.cache_expiry_hours = config.get('cache_expiry_hours', 1)
        self.force_refresh = config.get('force_refresh', False)
        
        # 创建缓存目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"NewsNowFetcher 初始化完成 - API: {self.api_base_url}, 调试模式: {self.debug_mode}")
    
    def get_name(self) -> str:
        """获取插件名称"""
        return "NewsNowFetcher"
    
    def get_version(self) -> str:
        """获取插件版本"""
        return "1.0.0"
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置插件"""
        try:
            self.api_base_url = config.get('api_base_url', self.api_base_url)
            self.debug_mode = config.get('debug_mode', self.debug_mode)
            self.force_refresh = config.get('force_refresh', self.force_refresh)
            self.cache_dir = Path(config.get('cache_dir', self.cache_dir))
            self.cache_expiry_hours = config.get('cache_expiry_hours', self.cache_expiry_hours)
            
            # 创建缓存目录
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"NewsNowFetcher 配置完成")
            return True
        except Exception as e:
            logger.error(f"NewsNowFetcher 配置失败: {str(e)}")
            return False
    
    def supports_platform(self, platform_type: str) -> bool:
        """检查是否支持指定类型的平台"""
        return platform_type.lower() in self.PLATFORM_MAPPING
    
    def fetch_data(
        self,
        platform: PlatformConfig,
        max_retries: int = 2,
        timeout: int = 30
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        抓取数据
        
        Args:
            platform: 平台配置
            max_retries: 最大重试次数
            timeout: 超时时间
            
        Returns:
            (error_msg, data) 元组
        """
        platform_type = platform.type.lower()
        platform_id = self.PLATFORM_MAPPING.get(platform_type, platform_type)
        
        logger.info(f"开始抓取平台数据: {platform.name} ({platform_type}) -> {platform_id}")
        
        # 调试模式优先使用本地测试数据
        if self.debug_mode and not self.force_refresh:
            cached_data = self._load_test_data(platform_type)
            if cached_data:
                logger.info(f"使用本地测试数据: {platform_type}")
                return None, cached_data
        
        # 检查缓存
        if not self.force_refresh:
            cached_data = self._load_cached_data(platform_id)
            if cached_data:
                logger.info(f"使用缓存数据: {platform_id}")
                return None, cached_data
        
        # 从API获取数据
        error_msg, data = self._fetch_from_api(platform_id, max_retries, timeout)
        if error_msg:
            # API失败时，尝试使用本地测试数据作为fallback
            if self.debug_mode:
                test_data = self._load_test_data(platform_type)
                if test_data:
                    logger.warning(f"API获取失败，使用测试数据: {error_msg}")
                    return None, test_data
            return error_msg, {}
        
        # 解析并标准化数据格式
        parsed_data = self._parse_api_response(platform_id, data)
        if not parsed_data:
            return f"数据解析失败: {platform_id}", {}
        
        # 缓存数据
        self._save_cached_data(platform_id, parsed_data)
        
        return None, parsed_data
    
    def _fetch_from_api(
        self,
        platform_id: str,
        max_retries: int = 2,
        timeout: int = 30
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """从NewsNow API获取数据"""
        
        api_url = f"{self.api_base_url}?id={platform_id}"
        logger.info(f"请求NewsNow API: {api_url}")
        
        # 添加请求头
        headers = {
            'Referer': "https://newsnow.busiyi.world/",
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': "?0",
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': "empty",
            'sec-fetch-mode': "cors",
            'sec-fetch-site': "same-origin",
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        }
        
        error_msg, response = self.make_request(
            url=api_url,
            method='GET',
            headers=headers,
            timeout=timeout,
            max_retries=max_retries
        )
        
        if error_msg:
            return f"API请求失败: {error_msg}", {}
        
        # 解析JSON响应
        error_msg, data = self.parse_json_response(response)
        if error_msg:
            return f"数据解析失败: {error_msg}", {}
        
        # 验证数据格式
        is_valid, validation_error = self._validate_api_data(data)
        if not is_valid:
            return f"数据格式验证失败: {validation_error}", {}
        
        logger.info(f"成功获取API数据: {platform_id}, 条目数: {len(data.get('items', []))}")
        return None, data
    
    def _validate_api_data(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证API数据格式"""
        required_fields = ['status', 'id', 'items']
        
        for field in required_fields:
            if field not in data:
                return False, f"缺少必需字段: {field}"
        
        if not isinstance(data.get('items'), list):
            return False, "items字段必须是数组"
        
        return True, None
    
    def _load_test_data(self, platform_type: str) -> Optional[Dict[str, Any]]:
        """
        加载测试数据
        
        Args:
            platform_type: 平台类型
            
        Returns:
            测试数据或None
        """
        try:
            test_data_dir = Path("test_data")
            test_file = test_data_dir / f"{platform_type}.json"
            
            if not test_file.exists():
                logger.debug(f"测试数据文件不存在: {test_file}")
                return None
            
            with open(test_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            logger.info(f"加载测试数据: {platform_type}")
            # 直接解析测试数据为标准格式
            return self._parse_api_response(platform_type, raw_data)
            
        except Exception as e:
            logger.error(f"加载测试数据失败: {str(e)}")
            return None
    
    def _get_cache_file_path(self, platform_id: str) -> Path:
        """获取缓存文件路径"""
        today = datetime.now().strftime("%Y%m%d")
        return self.cache_dir / f"{platform_id}_{today}.json"
    
    def _load_cached_data(self, platform_id: str) -> Optional[Dict[str, Any]]:
        """加载缓存数据"""
        cache_file = self._get_cache_file_path(platform_id)
        
        if not cache_file.exists():
            return None
        
        try:
            # 检查缓存是否过期
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age > self.cache_expiry_hours * 3600:
                logger.debug(f"缓存已过期: {platform_id} ({file_age/3600:.1f}小时)")
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"使用缓存数据: {platform_id}")
                return data
        except Exception as e:
            logger.error(f"加载缓存失败: {cache_file} - {str(e)}")
            return None
    
    def _save_cached_data(self, platform_id: str, data: Dict[str, Any]) -> None:
        """保存缓存数据"""
        try:
            cache_file = self._get_cache_file_path(platform_id)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"缓存数据已保存: {platform_id}")
        except Exception as e:
            logger.error(f"保存缓存失败: {str(e)}")
    
    def parse_platform_data(self, platform: PlatformConfig, raw_data: Dict[str, Any]) -> CrawlResult:
        """解析平台数据为标准格式"""
        
        titles = []
        platform_name = self.get_platform_name(platform)
        
        items = raw_data.get('items', [])
        logger.info(f"解析 {platform_name} 数据，共 {len(items)} 条")
        
        for index, item in enumerate(items):
            try:
                title_data = self._parse_item(item, platform_name, index)
                if title_data:
                    titles.append(title_data)
            except Exception as e:
                logger.warning(f"解析条目失败 [{index}]: {str(e)}")
                continue
        
        # 创建爬取结果
        result = CrawlResult(
            platform_name=platform_name,
            platform_type=platform.type,
            titles=titles,
            crawl_time=get_beijing_time(),
            total_count=len(titles),
            success=True,
            message=f"成功获取 {len(titles)} 条数据"
        )
        
        logger.info(f"数据解析完成: {platform_name} - {len(titles)} 条有效数据")
        return result
    
    def _parse_item(self, item: Dict[str, Any], platform_name: str, index: int) -> Optional[TitleData]:
        """解析单个条目"""
        
        # 提取基本信息
        title = item.get('title', '').strip()
        if not title:
            logger.debug(f"空标题，跳过 [{index}]")
            return None
        
        # 提取URL
        url = item.get('url', '')
        mobile_url = item.get('mobileUrl', url)
        
        # 提取热度信息
        extra = item.get('extra', {})
        
        # 根据不同平台提取热度数据
        hot_value = self._extract_hot_value(extra, platform_name)
        rank = index + 1  # 默认排名为索引+1
        
        # 提取时间信息（如果有）
        created_time = self._extract_time_info(item, extra)
        
        # 构建标题数据
        title_data = TitleData(
            title=title,
            url=url,
            mobile_url=mobile_url,
            source_name=platform_name,
            is_new=False,  # 新标题检测由分析管道处理
            ranks=[rank],
            rank_display=f"第{rank}名",
            time_display=created_time or "刚刚",
            count=hot_value,
            extra_data=extra
        )
        
        return title_data
    
    def _extract_hot_value(self, extra: Dict[str, Any], platform_name: str) -> int:
        """提取热度值"""
        # 微博：info字段包含热度信息，如"91万热度"
        if 'info' in extra:
            info = extra['info']
            if '万热度' in info:
                try:
                    # 提取数字部分
                    match = re.search(r'(\d+(?:\.\d+)?)', info)
                    if match:
                        value = float(match.group(1))
                        return int(value * 10000)  # 转换为具体数值
                except Exception:
                    pass
        
        # 知乎：info字段包含热度信息，如"3089万热度"
        if 'info' in extra:
            info = extra['info']
            if '万热度' in info:
                try:
                    match = re.search(r'(\d+(?:\.\d+)?)', info)
                    if match:
                        value = float(match.group(1))
                        return int(value * 10000)
                except Exception:
                    pass
        
        # 默认返回0
        return 0
    
    def _extract_time_info(self, item: Dict[str, Any], extra: Dict[str, Any]) -> str:
        """提取时间信息"""
        # 尝试从extra中提取时间
        if 'hover' in extra:
            hover = extra['hover']
            # 简单的日期提取逻辑
            # 匹配类似"10月14日"的格式
            match = re.search(r'(\d+月\d+日)', hover)
            if match:
                return match.group(1)
            # 匹配类似"10月14日 13:58"的格式
            match = re.search(r'(\d+月\d+日\s+\d+:\d+)', hover)
            if match:
                return match.group(1)
        
        return ""
    
    def _parse_api_response(self, platform_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析API响应数据为标准格式
        
        Args:
            platform_id: 平台ID
            data: API响应数据
            
        Returns:
            标准化后的数据格式
        """
        try:
            result = {}
            
            # 检查API响应状态
            if data.get('status') not in ['success', 'cache']:
                logger.warning(f"API响应状态异常: {data.get('status')}")
                return result
            
            items = data.get('items', [])
            logger.info(f"解析 {platform_id} 数据，共 {len(items)} 个条目")
            
            for index, item in enumerate(items):
                title = item.get('title', '')
                if not title:
                    continue
                
                # 提取热度信息
                hot_value = self._extract_hot_value(item, platform_id)
                
                # 提取时间信息
                time_info = self._extract_time_info(item, data)
                
                # 构建URL
                url = item.get('url', '')
                mobile_url = item.get('mobileUrl', url)
                
                # 创建标准化数据
                title_key = f"{title}_{index}"  # 确保唯一性
                result[title_key] = {
                    'title': title,
                    'source_name': platform_id,
                    'ranks': [index + 1],  # 排名从1开始
                    'time_info': time_info,
                    'count': hot_value if isinstance(hot_value, int) else 1,
                    'url': url,
                    'mobile_url': mobile_url,
                    'hot_value': hot_value
                }
                
                logger.debug(f"解析条目 {index + 1}: {title[:50]}... 热度: {hot_value}")
            
            logger.info(f"数据解析完成，共 {len(result)} 个有效条目")
            return result
            
        except Exception as e:
            logger.error(f"解析API响应数据失败: {str(e)}")
            return {}
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        return {
            "type": "object",
            "properties": {
                "api_base_url": {
                    "type": "string",
                    "default": "https://newsnow.busiyi.world/api/s",
                    "description": "NewsNow API基础URL"
                },
                "debug_mode": {
                    "type": "boolean", 
                    "default": False,
                    "description": "调试模式，优先使用本地测试数据"
                },
                "cache_dir": {
                    "type": "string",
                    "default": "cache/newsnow",
                    "description": "缓存目录路径"
                },
                "cache_expiry_hours": {
                    "type": "integer",
                    "default": 1,
                    "description": "缓存过期时间（小时）"
                },
                "force_refresh": {
                    "type": "boolean",
                    "default": False,
                    "description": "强制刷新，忽略缓存"
                }
            }
        }
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """验证配置"""
        try:
            # 基础URL验证
            if not self.api_base_url:
                return False, "API基础URL不能为空"
            
            if not self.api_base_url.startswith(('http://', 'https://')):
                return False, "API基础URL必须是有效的HTTP(S)地址"
            
            # 缓存目录验证
            if not self.cache_dir:
                return False, "缓存目录不能为空"
            
            # 缓存时间验证
            if self.cache_expiry_hours < 0:
                return False, "缓存过期时间不能为负数"
            
            return True, None
            
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"