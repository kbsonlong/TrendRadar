"""
文本渲染器
"""
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

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
        
        self._configured = True
        logger.info(f"文本渲染器配置完成: {self.template_dir}")
        return True
    
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
            template_path = None
            template_content = None
            
            for ext in template_extensions:
                candidate_path = Path(self.template_dir) / f"{template_name}{ext}"
                if candidate_path.exists():
                    template_path = candidate_path
                    break
            
            if not template_path:
                logger.error(f"模板文件不存在，已尝试扩展名: {', '.join(template_extensions)}")
                return ""
            
            with open(template_path, 'r', encoding=self.encoding) as f:
                template_content = f.read()
            
            # 简单的模板替换（支持 {{variable}} 语法）
            rendered_content = self._simple_template_render(template_content, context)
            
            # 如果指定了输出路径，保存到文件
            if output_path:
                full_output_path = Path(self.output_dir) / output_path
                full_output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_output_path, 'w', encoding=self.encoding) as f:
                    f.write(rendered_content)
                
                logger.info(f"文本文件已保存: {full_output_path}")
            
            return rendered_content
            
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
            template_path = Path(self.template_dir) / f"{template_name}{ext}"
            if template_path.exists():
                return True
        
        return False
    
    def _simple_template_render(self, template: str, context: Dict[str, Any]) -> str:
        """简单的模板渲染（支持 {{variable}} 语法）"""
        result = template
        
        # 替换简单的变量
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (str, int, float)):
                result = result.replace(placeholder, str(value))
            elif isinstance(value, (list, dict)):
                # 对于复杂类型，转换为字符串表示
                result = result.replace(placeholder, str(value))
            else:
                result = result.replace(placeholder, "")
        
        return result