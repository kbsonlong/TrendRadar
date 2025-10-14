"""
企业微信通知器
"""
import json
import logging
from typing import Dict, Any, List, Optional

import requests

from .base_notifier import BaseNotifier
from src.core.utils import split_content_into_batches

logger = logging.getLogger(__name__)


class WeWorkNotifier(BaseNotifier):
    """企业微信通知器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.corp_id = None
        self.corp_secret = None
        self.agent_id = None
        self.access_token = None
        self.batch_size = 10
    
    def get_name(self) -> str:
        return "WeWorkNotifier"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'corp_id': {
                'type': 'string',
                'required': True,
                'description': '企业ID'
            },
            'corp_secret': {
                'type': 'string',
                'required': True,
                'description': '应用Secret'
            },
            'agent_id': {
                'type': 'integer',
                'required': True,
                'description': '应用ID'
            },
            'batch_size': {
                'type': 'integer',
                'required': False,
                'default': 10,
                'description': '批量发送大小'
            }
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置企业微信通知器"""
        if not self.validate_config(config):
            return False
        
        self.corp_id = config.get('corp_id')
        self.corp_secret = config.get('corp_secret')
        self.agent_id = config.get('agent_id')
        self.batch_size = config.get('batch_size', 10)
        
        if not all([self.corp_id, self.corp_secret, self.agent_id]):
            logger.error("企业微信配置参数不完整")
            return False
        
        # 获取访问令牌
        if not self._get_access_token():
            return False
        
        self._configured = True
        logger.info(f"企业微信通知器配置完成: {self.corp_id}")
        return True
    
    def send_notification(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> bool:
        """发送企业微信通知"""
        if not self._configured:
            logger.error("企业微信通知器未配置")
            return False
        
        try:
            # 构建消息内容
            message = self._build_message(title, content, url, **kwargs)
            
            # 发送请求
            response = requests.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self.access_token}",
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info(f"企业微信通知发送成功: {title}")
                    return True
                elif result.get('errcode') == 42001:  # access_token 过期
                    if self._get_access_token():
                        return self.send_notification(title, content, url, **kwargs)
                    else:
                        logger.error("企业微信访问令牌刷新失败")
                        return False
                else:
                    logger.error(f"企业微信通知发送失败: {result.get('errmsg', '未知错误')}")
                    return False
            else:
                logger.error(f"企业微信通知请求失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"企业微信通知发送异常: {str(e)}")
            return False
    
    def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[bool]:
        """批量发送企业微信通知"""
        results = []
        
        # 分批处理
        batches = split_content_into_batches(notifications, self.batch_size)
        
        for batch in batches:
            for notification in batch:
                result = self.send_notification(**notification)
                results.append(result)
        
        return results
    
    def supports_batch(self) -> bool:
        """支持批量发送"""
        return True
    
    def _get_access_token(self) -> bool:
        """获取企业微信访问令牌"""
        try:
            response = requests.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={
                    'corpid': self.corp_id,
                    'corpsecret': self.corp_secret
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    self.access_token = result.get('access_token')
                    logger.info("企业微信访问令牌获取成功")
                    return True
                else:
                    logger.error(f"企业微信访问令牌获取失败: {result.get('errmsg', '未知错误')}")
                    return False
            else:
                logger.error(f"企业微信访问令牌请求失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"企业微信访问令牌获取异常: {str(e)}")
            return False
    
    def _build_message(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建企业微信消息"""
        # 构建文本内容
        text_content = f"{title}\n\n{content}"
        
        if url:
            text_content += f"\n\n查看详情: {url}"
        
        message = {
            "touser": "@all",  # 发送给所有人
            "msgtype": "text",
            "agentid": self.agent_id,
            "text": {
                "content": text_content
            }
        }
        
        # 添加 @ 功能
        if kwargs.get('touser'):
            message["touser"] = kwargs['touser']
        
        if kwargs.get('toparty'):
            message["toparty"] = kwargs['toparty']
        
        if kwargs.get('totag'):
            message["totag"] = kwargs['totag']
        
        return message