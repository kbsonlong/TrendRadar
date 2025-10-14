"""
配置管理模块
"""
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/config.yaml")
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            logger.error(f"配置文件不存在: {self.config_path}")
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"成功加载配置文件: {self.config_path}")
                return config
        except yaml.YAMLError as e:
            logger.error(f"配置文件格式错误: {e}")
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            value = value.get(k)
            if value is None:
                return default
        return value
    
    def get_platforms(self) -> list:
        """获取平台配置"""
        return self.get('platforms', [])
    
    def get_notifier_config(self, notifier_type: str) -> Dict[str, Any]:
        """获取通知器配置"""
        return self.get(f'{notifier_type.upper()}_CONFIG', {})
    
    def get_frequency_words(self) -> List[str]:
        """获取频率词配置"""
        frequency_words_file = Path("config/frequency_words.txt")
        if not frequency_words_file.exists():
            logger.warning(f"频率词文件不存在: {frequency_words_file}")
            return []
        
        try:
            with open(frequency_words_file, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]
                logger.info(f"成功加载频率词: {len(words)} 个")
                return words
        except Exception as e:
            logger.error(f"加载频率词文件失败: {e}")
            return []
    
    def get_word_groups(self) -> List[Dict[str, Any]]:
        """获取词组配置"""
        keywords_config = self.get('keywords', {})
        word_groups = keywords_config.get('word_groups', [])
        
        # 转换格式为预期的字典格式
        formatted_groups = []
        for group in word_groups:
            if isinstance(group, list) and len(group) > 0:
                formatted_groups.append({
                    'word': group[0],
                    'required_words': group[1:] if len(group) > 1 else [],
                    'frequency_words': group[1:] if len(group) > 1 else []
                })
        
        return formatted_groups
    
    def get_filter_words(self) -> List[str]:
        """获取过滤词配置"""
        return self.get('FILTER_WORDS', [])
    
    def get_rank_threshold(self) -> int:
        """获取排名阈值"""
        return self.get('RANK_THRESHOLD', 50)
    
    def get_batch_send_interval(self) -> int:
        """获取批量发送间隔"""
        return self.get('BATCH_SEND_INTERVAL', 2)
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """获取代理配置"""
        return self.get('PROXY', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get('logging', {})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.get('crawler', {})
    
    def get_newsnow_config(self) -> Dict[str, Any]:
        """获取NewsNow API配置"""
        return self.get('newsnow', {})
    
    def get_html_report_config(self) -> Dict[str, Any]:
        """获取HTML报告配置"""
        return self.get('report.html', {})
    
    def get_text_report_config(self) -> Dict[str, Any]:
        """获取文本报告配置"""
        return self.get('report.text', {})
    
    def get_notification_configs(self) -> Dict[str, Any]:
        """获取通知配置"""
        return {
            'feishu': self.get('FEISHU_CONFIG', {}),
            'dingtalk': self.get('DINGTALK_CONFIG', {}),
            'wework': self.get('WEWORK_CONFIG', {}),
            'email': self.get('EMAIL_CONFIG', {})
        }
    
    def get_version(self) -> str:
        """获取版本号"""
        return self.get('version', '1.0.0')