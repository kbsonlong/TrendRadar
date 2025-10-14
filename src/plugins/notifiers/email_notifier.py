"""
邮件通知器
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Any, List, Optional

from .base_notifier import BaseNotifier
from src.core.utils import split_content_into_batches

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.smtp_server = None
        self.smtp_port = None
        self.username = None
        self.password = None
        self.from_email = None
        self.to_emails = None
        self.use_tls = True
        self.batch_size = 5
    
    def get_name(self) -> str:
        return "EmailNotifier"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'smtp_server': {
                'type': 'string',
                'required': True,
                'description': 'SMTP 服务器地址'
            },
            'smtp_port': {
                'type': 'integer',
                'required': True,
                'description': 'SMTP 端口'
            },
            'username': {
                'type': 'string',
                'required': True,
                'description': '用户名'
            },
            'password': {
                'type': 'string',
                'required': True,
                'description': '密码'
            },
            'from_email': {
                'type': 'string',
                'required': True,
                'description': '发件人邮箱'
            },
            'to_emails': {
                'type': 'array',
                'required': True,
                'description': '收件人邮箱列表'
            },
            'use_tls': {
                'type': 'boolean',
                'required': False,
                'default': True,
                'description': '是否使用 TLS'
            },
            'batch_size': {
                'type': 'integer',
                'required': False,
                'default': 5,
                'description': '批量发送大小'
            }
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """配置邮件通知器"""
        if not self.validate_config(config):
            return False
        
        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port')
        self.username = config.get('username')
        self.password = config.get('password')
        self.from_email = config.get('from_email')
        self.to_emails = config.get('to_emails', [])
        self.use_tls = config.get('use_tls', True)
        self.batch_size = config.get('batch_size', 5)
        
        if not all([self.smtp_server, self.smtp_port, self.username, 
                   self.password, self.from_email, self.to_emails]):
            logger.error("邮件配置参数不完整")
            return False
        
        # 验证邮箱格式
        if not self._validate_emails():
            return False
        
        self._configured = True
        logger.info(f"邮件通知器配置完成: {self.smtp_server}:{self.smtp_port}")
        return True
    
    def send_notification(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> bool:
        """发送邮件通知"""
        if not self._configured:
            logger.error("邮件通知器未配置")
            return False
        
        try:
            # 构建邮件消息
            msg = self._build_message(title, content, url, **kwargs)
            
            # 发送邮件
            return self._send_email(msg)
            
        except Exception as e:
            logger.error(f"邮件通知发送异常: {str(e)}")
            return False
    
    def send_batch_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[bool]:
        """批量发送邮件通知"""
        results = []
        
        # 分批处理
        batches = split_content_into_batches(notifications, self.batch_size)
        
        for batch in batches:
            # 合并多个通知为一个邮件
            combined_title = f"批量通知 ({len(batch)} 条)"
            combined_content = self._combine_notifications(batch)
            
            result = self.send_notification(combined_title, combined_content)
            results.extend([result] * len(batch))
        
        return results
    
    def supports_batch(self) -> bool:
        """支持批量发送"""
        return True
    
    def _validate_emails(self) -> bool:
        """验证邮箱格式"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        # 验证发件人
        if not re.match(email_pattern, self.from_email):
            logger.error(f"发件人邮箱格式无效: {self.from_email}")
            return False
        
        # 验证收件人
        for email in self.to_emails:
            if not re.match(email_pattern, email):
                logger.error(f"收件人邮箱格式无效: {email}")
                return False
        
        return True
    
    def _build_message(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        **kwargs
    ) -> MIMEMultipart:
        """构建邮件消息"""
        # 创建消息
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(title, 'utf-8')
        msg['From'] = Header(self.from_email, 'utf-8')
        msg['To'] = Header(', '.join(self.to_emails), 'utf-8')
        
        # 添加日期
        from email.utils import formatdate
        msg['Date'] = formatdate(localtime=True)
        
        # 构建 HTML 内容
        html_content = self._build_html_content(title, content, url)
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 构建纯文本内容
        text_content = f"{title}\n\n{content}"
        if url:
            text_content += f"\n\n查看详情: {url}"
        
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        return msg
    
    def _build_html_content(
        self,
        title: str,
        content: str,
        url: Optional[str] = None
    ) -> str:
        """构建 HTML 内容"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
                h1 {{ color: #333; }}
                .content {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
                .link {{ margin-top: 20px; }}
                a {{ color: #007bff; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="content">
                <p>{content}</p>
            </div>
        """
        
        if url:
            html += f'<div class="link"><a href="{url}">查看详情</a></div>'
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _combine_notifications(self, notifications: List[Dict[str, Any]]) -> str:
        """合并多个通知"""
        combined_content = ""
        for i, notification in enumerate(notifications, 1):
            title = notification.get('title', '')
            content = notification.get('content', '')
            url = notification.get('url', '')
            
            combined_content += f"\n{i}. {title}\n"
            combined_content += f"   {content}\n"
            if url:
                combined_content += f"   链接: {url}\n"
        
        return combined_content.strip()
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """发送邮件"""
        try:
            # 连接 SMTP 服务器
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            
            # 登录
            server.login(self.username, self.password)
            
            # 发送邮件
            server.send_message(msg)
            
            # 关闭连接
            server.quit()
            
            logger.info(f"邮件发送成功: {msg['Subject']}")
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP 错误: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"邮件发送失败: {str(e)}")
            return False