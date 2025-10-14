"""
文本渲染器
"""
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
except ImportError:
    Environment = None
    FileSystemLoader = None
    TemplateNotFound = None

from .base_renderer import BaseRenderer

logger = logging.getLogger(__name__)


class TextRenderer(BaseRenderer):
    """文本渲染器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.template_dir = None
        self.output_dir = None
    
    def get_name(self) -> str:
        return "TextRenderer"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'template_dir': {
                'type': 'string',
                'required': True,
                'description': '模板目录路径'
            },
            'output_dir': {
                'type': 'string',
                'required': False,
                'default': 'output/text',
                'description': '输出目录路径'
            },
            'encoding': {
                'type': 'string',
                'required': False,
                'default': 'utf-8',
                'description': '文件编码'
            }
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置文本渲染器"""
        if not self.validate_config(config):
            return False
        
        if Environment is None:
            logger.error("Jinja2 未安装，请先安装: pip install jinja2")
            return False
        
        self.template_dir = config.get('template_dir')
        self.output_dir = config.get('output_dir', 'output/text')
        self.encoding = config.get('encoding', 'utf-8')
        
        if not self.template_dir:
            logger.error("模板目录不能为空")
            return False
        
        # 确保模板目录存在
        template_path = Path(self.template_dir)
        if not template_path.exists():
            logger.error(f"模板目录不存在: {self.template_dir}")
            return False
        
        # 确保输出目录存在
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # 初始化 Jinja2 环境
            self.env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=False,  # 文本不需要HTML转义
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # 添加自定义过滤器
            self._add_custom_filters()
            
            self._configured = True
            logger.info(f"文本渲染器配置完成: {self.template_dir}")
            return True
            
        except Exception as e:
            logger.error(f"文本渲染器配置失败: {str(e)}")
            return False
    
    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """渲染文本内容"""
        if not self._configured:
            logger.error("文本渲染器未配置")
            return ""
        
        try:
            # 尝试不同的模板文件扩展名
            template_extensions = ['.md', '.txt', '.markdown']
            template_file = None
            
            for ext in template_extensions:
                candidate_file = f"{template_name}{ext}"
                try:
                    template = self.env.get_template(candidate_file)
                    template_file = candidate_file
                    break
                except TemplateNotFound:
                    continue
            
            if not template_file:
                logger.error(f"模板文件不存在，已尝试扩展名: {', '.join(template_extensions)}")
                return ""
            
            # 渲染内容
            rendered_content = template.render(**context)
            
            # 如果指定了输出路径，保存到文件
            if output_path:
                full_output_path = Path(self.output_dir) / output_path
                full_output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_output_path, 'w', encoding=self.encoding) as f:
                    f.write(rendered_content)
                
                logger.info(f"文本文件已保存: {full_output_path}")
            
            return rendered_content
            
        except TemplateNotFound:
            logger.error(f"模板未找到: {template_name}")
            return ""
        except Exception as e:
            logger.error(f"文本渲染失败: {str(e)}")
            return ""
    
    def get_supported_formats(self) -> list[str]:
        """支持文本格式"""
        return ["txt", "markdown", "md"]
    
    def validate_template(self, template_name: str) -> bool:
        """验证模板是否存在"""
        if not self._configured:
            return False
        
        template_extensions = ['.md', '.txt', '.markdown']
        for ext in template_extensions:
            try:
                self.env.get_template(f"{template_name}{ext}")
                return True
            except TemplateNotFound:
                continue
        
        return False
    
    def _add_custom_filters(self):
        """添加自定义过滤器"""
        def format_time(value, format='%Y-%m-%d %H:%M:%S'):
            """格式化时间"""
            if hasattr(value, 'strftime'):
                return value.strftime(format)
            return str(value)
        
        def truncate_text(value, length=100, suffix='...'):
            """截断文本"""
            if len(value) <= length:
                return value
            return value[:length] + suffix
        
        def safe_url(value):
            """安全的 URL"""
            if not value or not value.startswith(('http://', 'https://')):
                return '#'
            return value
        
        # 注册过滤器
        self.env.filters['format_time'] = format_time
        self.env.filters['truncate_text'] = truncate_text
        self.env.filters['safe_url'] = safe_url