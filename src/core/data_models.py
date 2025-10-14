"""
数据模型模块
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TitleData:
    """标题数据模型"""
    title: str
    source_name: str
    is_new: bool = False
    ranks: List[int] = field(default_factory=list)
    rank_display: str = ""
    time_display: str = ""
    count: int = 1
    url: str = ""
    mobile_url: str = ""
    
    def __post_init__(self):
        if self.ranks is None:
            self.ranks = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'title': self.title,
            'source_name': self.source_name,
            'is_new': self.is_new,
            'ranks': self.ranks,
            'rank_display': self.rank_display,
            'time_display': self.time_display,
            'count': self.count,
            'url': self.url,
            'mobile_url': self.mobile_url
        }


@dataclass
class WordStat:
    """词频统计模型"""
    word: str
    count: int
    titles: List[TitleData] = field(default_factory=list)
    
    def __post_init__(self):
        if self.titles is None:
            self.titles = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'word': self.word,
            'count': self.count,
            'titles': [title.to_dict() for title in self.titles]
        }


@dataclass
class ReportData:
    """报告数据模型"""
    stats: List[WordStat] = field(default_factory=list)
    new_titles: Dict[str, List[TitleData]] = field(default_factory=dict)
    failed_ids: List[str] = field(default_factory=list)
    total_new_count: int = 0
    update_info: Optional[Dict[str, Any]] = None
    generation_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = []
        if self.new_titles is None:
            self.new_titles = {}
        if self.failed_ids is None:
            self.failed_ids = []
        
        # 计算总新增标题数
        self.total_new_count = sum(len(titles) for titles in self.new_titles.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stats': [stat.to_dict() for stat in self.stats],
            'new_titles': {
                source: [title.to_dict() for title in titles]
                for source, titles in self.new_titles.items()
            },
            'failed_ids': self.failed_ids,
            'total_new_count': self.total_new_count,
            'update_info': self.update_info,
            'generation_time': self.generation_time
        }
    
    def get_total_titles(self) -> int:
        """获取总标题数"""
        return sum(len(stat.titles) for stat in self.stats)


@dataclass
class PlatformConfig:
    """平台配置模型"""
    id: str
    name: str
    url: str
    type: str = "news"
    enabled: bool = True
    headers: Optional[Dict[str, str]] = field(default_factory=dict)
    timeout: int = 30
    max_retries: int = 2
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'type': self.type,
            'enabled': self.enabled,
            'headers': self.headers,
            'timeout': self.timeout,
            'max_retries': self.max_retries
        }


@dataclass
class CrawlResult:
    """抓取结果模型"""
    platform_id: str
    platform_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None
    crawl_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'platform_id': self.platform_id,
            'platform_name': self.platform_name,
            'success': self.success,
            'data': self.data,
            'error_msg': self.error_msg,
            'crawl_time': self.crawl_time
        }


@dataclass
class NotificationResult:
    """通知结果模型"""
    platform: str
    success: bool
    error_msg: Optional[str] = None
    send_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    batch_info: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.batch_info is None:
            self.batch_info = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'platform': self.platform,
            'success': self.success,
            'error_msg': self.error_msg,
            'send_time': self.send_time,
            'batch_info': self.batch_info
        }