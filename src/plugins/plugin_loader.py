"""
插件管理器 - 负责加载和管理所有插件
"""
import os
import importlib
import logging
from typing import Dict, List, Type, Optional, Any
from pathlib import Path

from .base import BasePlugin, PluginManager

logger = logging.getLogger(__name__)


class PluginLoader:
    """插件加载器"""
    
    def __init__(self):
        self.fetcher_plugins: Dict[str, Type[BasePlugin]] = {}
        self.notifier_plugins: Dict[str, Type[BasePlugin]] = {}
        self.renderer_plugins: Dict[str, Type[BasePlugin]] = {}
    
    def load_plugins_from_directory(self, plugin_dir: str, plugin_type: str) -> Dict[str, Type[BasePlugin]]:
        """从指定目录加载插件"""
        plugins = {}
        plugin_path = Path(plugin_dir)
        
        if not plugin_path.exists():
            logger.warning(f"插件目录不存在: {plugin_dir}")
            return plugins
        
        # 遍历目录中的 Python 文件
        for py_file in plugin_path.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "base.py" or py_file.name.startswith("base_"):
                continue
            
            try:
                # 动态导入模块
                module_name = f"src.plugins.{plugin_type}.{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    
                    # 添加到 sys.modules 以便相对导入正常工作
                    import sys
                    sys.modules[module_name] = module
                    
                    spec.loader.exec_module(module)
                    
                    # 查找插件类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BasePlugin) and 
                            attr != BasePlugin and
                            not attr.__name__.startswith('Base')):
                            
                            plugin_instance = attr({})
                            plugin_name = plugin_instance.get_name()
                            plugins[plugin_name] = attr
                            logger.info(f"加载插件成功: {plugin_name} ({plugin_type})")
                            break
                            
            except Exception as e:
                logger.error(f"加载插件失败 {py_file.name}: {str(e)}")
        
        return plugins
    
    def load_all_plugins(self, base_plugin_dir: str = "src/plugins") -> None:
        """加载所有插件"""
        base_path = Path(base_plugin_dir)
        
        # 加载抓取器插件
        fetcher_dir = base_path / "fetchers"
        self.fetcher_plugins = self.load_plugins_from_directory(
            str(fetcher_dir), "fetchers"
        )
        
        # 加载通知器插件
        notifier_dir = base_path / "notifiers"
        self.notifier_plugins = self.load_plugins_from_directory(
            str(notifier_dir), "notifiers"
        )
        
        # 加载渲染器插件
        renderer_dir = base_path / "renderers"
        self.renderer_plugins = self.load_plugins_from_directory(
            str(renderer_dir), "renderers"
        )
        
        logger.info(f"插件加载完成 - 抓取器: {len(self.fetcher_plugins)}, "
                   f"通知器: {len(self.notifier_plugins)}, "
                   f"渲染器: {len(self.renderer_plugins)}")
    
    def get_fetcher_plugin(self, name: str) -> Optional[Type[BasePlugin]]:
        """获取指定名称的抓取器插件"""
        return self.fetcher_plugins.get(name)
    
    def get_notifier_plugin(self, name: str) -> Optional[Type[BasePlugin]]:
        """获取指定名称的通知器插件"""
        return self.notifier_plugins.get(name)
    
    def get_renderer_plugin(self, name: str) -> Optional[Type[BasePlugin]]:
        """获取指定名称的渲染器插件"""
        return self.renderer_plugins.get(name)
    
    def list_available_plugins(self) -> Dict[str, List[str]]:
        """列出所有可用插件"""
        return {
            "fetchers": list(self.fetcher_plugins.keys()),
            "notifiers": list(self.notifier_plugins.keys()),
            "renderers": list(self.renderer_plugins.keys())
        }