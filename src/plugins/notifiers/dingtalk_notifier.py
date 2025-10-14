"""
钉钉通知器
"""
import base64
import hashlib
import json
import logging
import time
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

import requests

from .base_notifier import BaseNotifier
from src.core.utils import split_content_into_batches

logger = logging.getLogger(__name__)


class DingTalkNotifier(BaseNotifier):
    """钉钉通知器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.webhook_url = None
        self.secret = None
        self.batch_size = 10
        self.batch_interval = 1  # 秒
    
    def get_name(self) -> str:
        return "DingTalkNotifier"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'webhook_url': {
                'type': 'string',
                'required': True,
                'description': '钉钉 Webhook URL'
            },
            'secret': {
                'type': 'string',
                'required': False,
                'description': '钉钉密钥（可选）'
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
        """配置钉钉通知器"""
        if not self.validate_config(config):
            return False
        
        self.webhook_url = config.get('webhook_url')
        self.secret = config.get('secret')
        self.batch_size = config.get('batch_size', 10)
        self.batch_interval = config.get('batch_interval', 1)
        
        if not self.webhook_url:
            logger.error("钉钉 Webhook URL 不能为空")
            return False
        
        self._configured = True
        logger.info(f"钉钉通知器配置完成: {self.webhook_url}")
        return True
    
    def send_notification(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> bool:
        """发送钉钉通知"""
        if not self._configured:
            logger.error("钉钉通知器未配置")
            return False
        
        try:
            # 构建消息内容
            message = self._build_message(title, content, url, **kwargs)
            
            # 构建带签名的 URL（如果需要）
            webhook_url = self._build_signed_url() if self.secret else self.webhook_url
            
            # 发送请求
            response = requests.post(
                webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info(f"钉钉通知发送成功: {title}")
                    return True
                else:
                    logger.error(f"钉钉通知发送失败: {result.get('errmsg', '未知错误')}")
                    return False
            else:
                logger.error(f"钉钉通知请求失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"钉钉通知发送异常: {str(e)}")
            return False
    
    def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[bool]:
        """批量发送钉钉通知"""
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
    
    def _build_signed_url(self) -> str:
        """构建带签名的钉钉 URL"""
        timestamp = str(int(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f"{timestamp}\n{self.secret}"
        string_to_sign_enc = string_to_sign.encode('utf-8')
        
        hmac_code = hashlib.sha256(secret_enc)
        hmac_code.update(string_to_sign_enc)
        sign = quote_plus(base64.b64encode(hmac_code.digest()).decode('utf-8'))
        
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
    
    def _build_message(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建钉钉消息"""
        # 构建 Markdown 格式内容
        markdown_content = f"### {title}\n\n{content}"
        
        if url:
            markdown_content += f"\n\n[查看详情]({url})"
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown_content
            }
        }
        
        # 添加 @ 功能
        if kwargs.get('at_mobiles'):
            message["at"] = {
                "atMobiles": kwargs['at_mobiles'],
                "isAtAll": False
            }
        
        if kwargs.get('at_all'):
            message["at"] = {
                "isAtAll": True
            }
        
        return message