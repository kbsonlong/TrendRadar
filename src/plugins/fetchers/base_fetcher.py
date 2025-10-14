"""
数据抓取器基类
"""
from abc import abstractmethod
from typing import Dict, Any, List, Tuple, Optional
import logging
import time
import requests
from urllib.parse import urljoin, urlparse

from ..base import BasePlugin
from src.core.data_models import PlatformConfig, CrawlResult
from src.core.utils import detect_proxy, get_beijing_time

logger = logging.getLogger(__name__)


class BaseFetcher(BasePlugin):
    """数据抓取器基类"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.session = None
        self.proxy_settings = detect_proxy()
        self._setup_session()
    
    def _setup_session(self):
        """设置 HTTP 会话"""
        self.session = requests.Session()
        
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': self.get_config('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # 设置代理
        if self.proxy_settings:
            self.session.proxies.update(self.proxy_settings)
            logger.info(f"设置代理: {self.proxy_settings}")
    
    @abstractmethod
    def fetch_data(
        self,
        platform: PlatformConfig,
        max_retries: int = 2,
        timeout: int = 30
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        抓取数据
        
        Args:
            platform: 平台配置
            max_retries: 最大重试次数
            timeout: 超时时间
            
        Returns:
            (error_msg, data) 元组
            error_msg: 错误信息，成功时为 None
            data: 抓取到的数据
        """
        pass
    
    @abstractmethod
    def supports_platform(self, platform_type: str) -> bool:
        """检查是否支持指定类型的平台"""
        pass
    
    def get_platform_name(self, platform: PlatformConfig) -> str:
        """获取平台名称"""
        return platform.name or platform.id
    
    def make_request(
        self,
        url: str,
        method: str = 'GET',
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        max_retries: int = 2
    ) -> Tuple[Optional[str], requests.Response]:
        """发送 HTTP 请求"""
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"请求尝试 {attempt + 1}/{max_retries + 1}: {method} {url}")
                
                request_headers = self.session.headers.copy()
                if headers:
                    request_headers.update(headers)
                
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    data=data,
                    timeout=timeout,
                    allow_redirects=True
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    logger.debug(f"请求成功: {url}")
                    return None, response
                elif response.status_code == 429:
                    # 速率限制
                    logger.warning(f"速率限制，等待重试: {url}")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)  # 指数退避
                        continue
                    else:
                        return f"速率限制，重试失败: {response.status_code}", response
                else:
                    error_msg = f"HTTP错误: {response.status_code}"
                    logger.warning(f"{error_msg}: {url}")
                    if attempt < max_retries:
                        time.sleep(1)
                        continue
                    else:
                        return error_msg, response
                        
            except requests.exceptions.Timeout:
                error_msg = "请求超时"
                logger.warning(f"{error_msg}: {url}")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                else:
                    return error_msg, None
                    
            except requests.exceptions.ConnectionError as e:
                error_msg = f"连接错误: {str(e)}"
                logger.warning(f"{error_msg}: {url}")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                else:
                    return error_msg, None
                    
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                logger.error(f"{error_msg}: {url}")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                else:
                    return error_msg, None
        
        return "所有重试均失败", None
    
    def parse_json_response(self, response: requests.Response) -> Tuple[Optional[str], Any]:
        """解析 JSON 响应"""
        try:
            data = response.json()
            return None, data
        except Exception as e:
            error_msg = f"JSON解析失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, None
    
    def validate_data(self, data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, Optional[str]]:
        """验证数据完整性"""
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            error_msg = f"缺少必需字段: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return False, error_msg
        
        return True, None
    
    def cleanup(self):
        """清理资源"""
        if self.session:
            self.session.close()
            logger.info("HTTP会话已关闭")
        super().cleanup()