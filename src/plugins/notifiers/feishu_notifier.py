"""
飞书通知器
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional

import requests

from .base_notifier import BaseNotifier
from src.core.utils import split_content_into_batches

logger = logging.getLogger(__name__)


class FeishuNotifier(BaseNotifier):
    """飞书通知器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.webhook_url = None
        self.secret = None
        self.batch_size = 10
        self.batch_interval = 1  # 秒
    
    def get_name(self) -> str:
        return "FeishuNotifier"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'webhook_url': {
                'type': 'string',
                'required': True,
                'description': '飞书 Webhook URL'
            },
            'secret': {
                'type': 'string',
                'required': False,
                'description': '飞书密钥（可选）'
            },
            'batch_size': {
                'type': 'integer',
                'required': False,
                'default': 10,
                'description': '批量发送大小'
            },
            'batch_interval': {
                'type': 'integer',
                'required': False,
                'default': 1,
                'description': '批量发送间隔（秒）'
            }
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置飞书通知器"""
        if not self.validate_config(config):
            return False
        
        self.webhook_url = config.get('webhook_url')
        self.secret = config.get('secret')
        self.batch_size = config.get('batch_size', 10)
        self.batch_interval = config.get('batch_interval', 1)
        
        if not self.webhook_url:
            logger.error("飞书 Webhook URL 不能为空")
            return False
        
        self._configured = True
        logger.info(f"飞书通知器配置完成: {self.webhook_url}")
        return True
    
    def send_notification(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> bool:
        """发送飞书通知"""
        if not self._configured:
            logger.error("飞书通知器未配置")
            return False
        
        try:
            # 构建消息内容
            message = self._build_message(title, content, url, **kwargs)
            
            # 发送请求
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"飞书通知发送成功: {title}")
                    return True
                else:
                    logger.error(f"飞书通知发送失败: {result.get('msg', '未知错误')}")
                    return False
            else:
                logger.error(f"飞书通知请求失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"飞书通知发送异常: {str(e)}")
            return False
    
    def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[bool]:
        """批量发送飞书通知"""
        results = []
        
        # 分批处理
        batches = split_content_into_batches(notifications, self.batch_size)
        
        for i, batch in enumerate(batches):
            if i > 0:
                time.sleep(self.batch_interval)  # 间隔发送
            
            for notification in batch:
                result = self.send_notification(**notification)
                results.append(result)
        
        return results
    
    def supports_batch(self) -> bool:
        """支持批量发送"""
        return True
    
    def _build_message(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建飞书消息"""
        message = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [
                            [
                                {
                                    "tag": "text",
                                    "text": content
                                }
                            ]
                        ]
                    }
                }
            }
        }
        
        # 添加链接
        if url:
            message["content"]["post"]["zh_cn"]["content"][0].append({
                "tag": "a",
                "text": "查看详情",
                "href": url
            })
        
        # 添加额外信息
        if kwargs.get('color'):
            # 飞书支持的颜色主题
            message["content"]["post"]["zh_cn"]["title"] = f"[{kwargs['color']}]{title}[/]"
        
        return message