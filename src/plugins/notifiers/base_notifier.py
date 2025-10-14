"""
通知器基类和接口
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..base import BasePlugin

logger = logging.getLogger(__name__)


class BaseNotifier(BasePlugin, ABC):
    """通知器基类"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self._configured = False
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> bool:
        """
        配置通知器
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否成功
        """
        pass
    
    @abstractmethod
    def send_notification(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
            url: 可选的链接
            **kwargs: 其他参数
            
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @abstractmethod
    def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[bool]:
        """
        批量发送通知
        
        Args:
            notifications: 通知列表，每个通知包含 title, content, url 等
            
        Returns:
            List[bool]: 每个通知的发送结果
        """
        pass
    
    @abstractmethod
    def supports_batch(self) -> bool:
        """
        是否支持批量发送
        
        Returns:
            bool: 是否支持批量发送
        """
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取配置模式
        
        Returns:
            Dict[str, Any]: 配置模式定义
        """
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        schema = self.get_config_schema()
        if not schema:
            return True
        
        # 基本验证：检查必需字段
        for field, field_schema in schema.items():
            if field_schema.get('required', False) and field not in config:
                logger.error(f"配置缺少必需字段: {field}")
                return False
        
        return True
    
    def cleanup(self) -> None:
        """清理资源"""
        self._configured = False
        logger.info(f"通知器清理完成: {self.get_name()}")