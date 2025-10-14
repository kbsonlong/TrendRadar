"""
工具函数模块
"""
import re
import html
import logging
from datetime import datetime, timezone, timedelta
import json
from typing import Dict, Any, Optional, List
import os
import time
from .data_models import TitleData

logger = logging.getLogger(__name__)


# 版本信息
VERSION = "2.0.0"


def get_beijing_time() -> datetime:
    """获取北京时间"""
    utc_time = datetime.now(timezone.utc)
    beijing_time = utc_time + timedelta(hours=8)
    return beijing_time


def format_beijing_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化北京时间"""
    return get_beijing_time().strftime(format_str)


def clean_title(title: str) -> str:
    """清洗标题"""
    if not title:
        return ""
    
    # 移除多余的空白字符
    title = re.sub(r'\s+', ' ', title.strip())
    
    # 移除特殊字符（保留中文、英文、数字、常见标点）
    title = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\-_.，。！？：；""''（）()【】\[\]]', '', title)
    
    # 移除 HTML 标签
    title = re.sub(r'<[^>]+>', '', title)
    
    # 移除多余的空格
    title = re.sub(r'\s+', ' ', title.strip())
    
    return title


def html_escape(text: str) -> str:
    """HTML 转义"""
    return html.escape(text)


def is_first_crawl_today() -> bool:
    """检查今天是否首次抓取"""
    today = get_beijing_time().date()
    record_file = Path("output/logs/crawl_record.txt")
    
    if not record_file.exists():
        return True
    
    try:
        with open(record_file, 'r', encoding='utf-8') as f:
            last_crawl = f.read().strip()
            if last_crawl:
                last_date = datetime.strptime(last_crawl, "%Y-%m-%d").date()
                return last_date < today
    except Exception as e:
        logger.warning(f"读取抓取记录失败: {e}")
    
    return True


def save_crawl_record():
    """保存抓取记录"""
    today = get_beijing_time().date()
    record_file = Path("output/logs/crawl_record.txt")
    
    try:
        record_file.parent.mkdir(parents=True, exist_ok=True)
        with open(record_file, 'w', encoding='utf-8') as f:
            f.write(str(today))
        logger.info(f"保存抓取记录: {today}")
    except Exception as e:
        logger.error(f"保存抓取记录失败: {e}")


def load_frequency_words(file_path: str = "config/frequency_words.txt") -> List[str]:
    """加载频率词"""
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"频率词文件不存在: {file_path}")
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logger.info(f"加载频率词: {len(words)} 个")
            return words
    except Exception as e:
        logger.error(f"加载频率词失败: {e}")
        return []


def detect_proxy() -> Optional[Dict[str, str]]:
    """检测代理设置"""
    proxy_settings = {}
    
    # 检查环境变量
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    
    if http_proxy:
        proxy_settings['http'] = http_proxy
    if https_proxy:
        proxy_settings['https'] = https_proxy
    
    if proxy_settings:
        logger.info(f"检测到代理设置: {proxy_settings}")
    
    return proxy_settings if proxy_settings else None


def split_content_into_batches(
    content: str,
    max_size: int = 4000,
    separator: str = "\n\n"
) -> List[str]:
    """将内容分批"""
    if len(content) <= max_size:
        return [content]
    
    batches = []
    current_batch = ""
    
    # 按分隔符分割内容
    parts = content.split(separator)
    
    for part in parts:
        if len(current_batch) + len(part) + len(separator) <= max_size:
            if current_batch:
                current_batch += separator + part
            else:
                current_batch = part
        else:
            if current_batch:
                batches.append(current_batch)
            current_batch = part
    
    if current_batch:
        batches.append(current_batch)
    
    logger.info(f"内容分批完成: {len(batches)} 批，最大批次大小: {max_size}")
    return batches


def format_time_ago(time_str: str) -> str:
    """格式化时间差"""
    try:
        # 解析时间字符串
        if isinstance(time_str, str):
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        else:
            dt = time_str
        
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}小时前"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except Exception as e:
        logger.debug(f"时间格式化失败: {e}, 原值: {time_str}")
        return time_str


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + "..."


def safe_filename(filename: str) -> str:
    """生成安全的文件名"""
    # 移除不安全的字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 移除前导/尾随的点和空格
    filename = filename.strip('. ')
    # 限制长度
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename or "unnamed"


def ensure_directory(path: str) -> bool:
    """确保目录存在"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {path}, 错误: {e}")
        return False


class PushRecordManager:
    """推送记录管理器"""
    
    def __init__(self, record_file: str = "output/logs/push_records.json"):
        self.record_file = Path(record_file)
        self.records = self._load_records()
    
    def _load_records(self) -> Dict[str, Any]:
        """加载推送记录"""
        if not self.record_file.exists():
            return {}
        
        try:
            import json
            with open(self.record_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载推送记录失败: {e}")
            return {}
    
    def _save_records(self):
        """保存推送记录"""
        try:
            import json
            self.record_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存推送记录失败: {e}")
    
    def has_pushed_today(self, platform: str, content_hash: str) -> bool:
        """检查今天是否已经推送过"""
        today = get_beijing_time().strftime("%Y-%m-%d")
        key = f"{platform}:{today}"
        
        return content_hash in self.records.get(key, [])
    
    def mark_pushed_today(self, platform: str, content_hash: str):
        """标记今天已推送"""
        today = get_beijing_time().strftime("%Y-%m-%d")
        key = f"{platform}:{today}"
        
        if key not in self.records:
            self.records[key] = []
        
        if content_hash not in self.records[key]:
            self.records[key].append(content_hash)
            self._save_records()
            logger.info(f"记录推送: {platform} - {content_hash[:8]}...")


# 从 pathlib 导入 Path
from pathlib import Path


class TitleHistoryManager:
    """标题历史管理器"""
    
    def __init__(self, history_dir: str = "output/history"):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def get_history_file_path(self, date_str: str = None) -> Path:
        """获取历史文件路径"""
        if date_str is None:
            date_str = get_beijing_time().strftime("%Y%m%d")
        return self.history_dir / f"titles_{date_str}.json"
    
    def load_history_titles(self, date_str: str = None) -> Dict[str, List[str]]:
        """加载历史标题数据"""
        history_file = self.get_history_file_path(date_str)
        
        if not history_file.exists():
            self.logger.info(f"历史文件不存在: {history_file}")
            return {}
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.logger.info(f"加载历史标题数据: {len(data)} 个平台")
                return data
        except Exception as e:
            self.logger.error(f"加载历史标题失败: {e}")
            return {}
    
    def save_history_titles(self, titles_data: Dict[str, List[str]], date_str: str = None):
        """保存标题历史数据"""
        history_file = self.get_history_file_path(date_str)
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(titles_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"保存历史标题数据: {history_file}")
        except Exception as e:
            self.logger.error(f"保存历史标题失败: {e}")
    
    def identify_new_titles(self, current_data: Dict[str, Any], 
                           history_date: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """识别新标题
        
        Args:
            current_data: 当前爬取的数据
            history_date: 历史日期（默认昨天）
            
        Returns:
            新标题字典，格式为 {source_id: [TitleData, ...]}
        """
        if history_date is None:
            history_date = datetime.now() - timedelta(days=1)
            
        self.logger.info(f"识别新标题，历史日期: {history_date}")
        
        # 将datetime转换为字符串格式用于文件路径
        history_date_str = history_date.strftime("%Y%m%d")
        
        # 加载历史标题
        historical_titles = self.load_history_titles(history_date_str)
        self.logger.info(f"历史标题数量: {len(historical_titles)}")
        
        new_titles = {}
        total_new_count = 0
        
        # 遍历当前数据
        for source_id, items in current_data.items():
            source_new_titles = []
            
            # 获取该平台的历史标题列表
            platform_historical_titles = historical_titles.get(source_id, [])
            self.logger.debug(f"平台 {source_id} 历史标题: {len(platform_historical_titles)} 个")
            
            # 处理字典格式数据: {title: title_info}
            if isinstance(items, dict):
                for title, title_info in items.items():
                    # 检查是否是新标题
                    if title not in platform_historical_titles:
                        self.logger.debug(f"发现新标题: {title[:50]}...")
                        
                        # 获取标题信息
                        if isinstance(title_info, dict):
                            title_data = TitleData(
                                title=title,
                                source_name=title_info.get('source_name', source_id),
                                url=title_info.get('url', ''),
                                mobile_url=title_info.get('mobile_url', ''),
                                time_display=title_info.get('time_info', ''),
                                ranks=title_info.get('ranks', []),
                                is_new=True
                            )
                        else:
                            title_data = TitleData(
                                title=title,
                                source_name=source_id,
                                is_new=True
                            )
                        
                        source_new_titles.append(title_data)
                        total_new_count += 1
            
            # 处理列表格式数据: [{title_data}, ...]
            elif isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                        
                    title = item.get('title', '')
                    if not title:
                        continue
                        
                    # 检查是否是新标题
                    if title not in platform_historical_titles:
                        self.logger.debug(f"发现新标题: {title[:50]}...")
                        title_data = TitleData(
                            title=title,
                            source_name=item.get('source_name', source_id),
                            url=item.get('url', ''),
                            mobile_url=item.get('mobile_url', ''),
                            time_display=item.get('time_info', ''),
                            is_new=True
                        )
                        source_new_titles.append(title_data)
                        total_new_count += 1
            
            if source_new_titles:
                new_titles[source_id] = source_new_titles
                self.logger.info(f"平台 {source_id} 发现 {len(source_new_titles)} 个新标题")
                
        self.logger.info(f"新标题识别完成，总计: {total_new_count} 个")
        return new_titles
    
    def extract_titles_for_history(self, data_source: Dict[str, Any]) -> Dict[str, List[str]]:
        """从数据源中提取标题列表用于历史记录"""
        history_data = {}
        
        for source_id, titles_info in data_source.items():
            if isinstance(titles_info, dict):
                # 只保存标题文本列表
                history_data[source_id] = list(titles_info.keys())
            elif isinstance(titles_info, list):
                # 如果数据是列表格式，提取每个项目的标题
                titles = []
                for item in titles_info:
                    if isinstance(item, dict) and 'title' in item:
                        titles.append(item['title'])
                    elif isinstance(item, str):
                        titles.append(item)
                history_data[source_id] = titles
        
        return history_data