"""
渲染器基类和接口
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from ..base import BasePlugin

logger = logging.getLogger(__name__)


class BaseRenderer(BasePlugin, ABC):
    """渲染器基类"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self._configured = False
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> bool:
        """
        配置渲染器
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否成功
        """
        pass
    
    @abstractmethod
    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        渲染内容
        
        Args:
            template_name: 模板名称
            context: 渲染上下文数据
            output_path: 可选的输出文件路径
            
        Returns:
            str: 渲染后的内容
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """
        获取支持的输出格式
        
        Returns:
            list[str]: 支持的格式列表
        """
        pass
    
    @abstractmethod
    def validate_template(self, template_name: str) -> bool:
        """
        验证模板是否存在且有效
        
        Args:
            template_name: 模板名称
            
        Returns:
            bool: 模板是否有效
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
        logger.info(f"渲染器清理完成: {self.get_name()}")