"""
插件基类模块
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """插件基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.name = self.get_name()
        self.version = self.get_version()
        logger.info(f"初始化插件: {self.name} v{self.version}")
    
    @abstractmethod
    def get_name(self) -> str:
        """获取插件名称"""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """获取插件版本"""
        pass
    
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self.enabled
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)
    
    def validate_config(self) -> bool:
        """验证配置（可选重写）"""
        return True
    
    def initialize(self) -> bool:
        """初始化插件（可选重写）"""
        try:
            if not self.validate_config():
                logger.error(f"插件 {self.name} 配置验证失败")
                return False
            
            logger.info(f"插件 {self.name} 初始化成功")
            return True
        except Exception as e:
            logger.error(f"插件 {self.name} 初始化失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源（可选重写）"""
        logger.info(f"插件 {self.name} 清理完成")


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        logger.info("初始化插件管理器")
    
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """注册插件"""
        try:
            if not plugin.initialize():
                logger.error(f"插件 {plugin.name} 初始化失败，注册中止")
                return False
            
            self.plugins[plugin.name] = plugin
            logger.info(f"插件注册成功: {plugin.name}")
            return True
        except Exception as e:
            logger.error(f"插件注册失败: {plugin.name}, 错误: {e}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """注销插件"""
        if plugin_name not in self.plugins:
            logger.warning(f"插件不存在: {plugin_name}")
            return False
        
        try:
            plugin = self.plugins[plugin_name]
            plugin.cleanup()
            del self.plugins[plugin_name]
            logger.info(f"插件注销成功: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"插件注销失败: {plugin_name}, 错误: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """获取插件"""
        return self.plugins.get(plugin_name)
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """获取启用的插件"""
        return [plugin for plugin in self.plugins.values() if plugin.is_enabled()]
    
    def get_all_plugins(self) -> List[BasePlugin]:
        """获取所有插件"""
        return list(self.plugins.values())
    
    def cleanup_all(self):
        """清理所有插件"""
        for plugin_name in list(self.plugins.keys()):
            self.unregister_plugin(plugin_name)
        logger.info("所有插件清理完成")