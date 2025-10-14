"""
TrendRadar - 趋势雷达主程序
重构版本 - 插件化架构
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.core.config import ConfigManager
from src.core.data_models import PlatformConfig, ReportData
from src.core.pipeline import AnalysisPipeline
from src.core.utils import (
    get_beijing_time, format_time_ago, ensure_directory,
    save_crawl_record, is_first_crawl_today
)
from src.plugins.plugin_loader import PluginLoader
from src.plugins.fetchers.news_fetcher import NewsFetcher
from src.plugins.notifiers.feishu_notifier import FeishuNotifier
from src.plugins.notifiers.dingtalk_notifier import DingTalkNotifier
from src.plugins.notifiers.wework_notifier import WeWorkNotifier
from src.plugins.notifiers.email_notifier import EmailNotifier
from src.plugins.renderers.html_renderer import HTMLRenderer
from src.plugins.renderers.text_renderer import TextRenderer


class TrendRadar:
    """趋势雷达主类"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_manager = ConfigManager(Path(config_path))
        self.plugin_loader = PluginLoader()
        self.analysis_pipeline = AnalysisPipeline(self.config_manager)
        
        # 初始化插件
        self.fetcher_plugins = {}
        self.notifier_plugins = {}
        self.renderer_plugins = {}
        
        # 设置日志
        self._setup_logging()
        
        logger = logging.getLogger(__name__)
        logger.info("TrendRadar 初始化完成")
    
    def _setup_logging(self):
        """设置日志配置"""
        log_config = self.config_manager.get_logging_config()
        
        # 确保日志目录存在
        log_file = log_config.get('file', 'output/logs/trendradar.log')
        ensure_directory(str(Path(log_file).parent))
        
        # 配置日志
        logging.basicConfig(
            level=getattr(logging, log_config.get('level', 'INFO')),
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def initialize_plugins(self):
        """初始化插件"""
        logger = logging.getLogger(__name__)
        logger.info("开始初始化插件...")
        
        # 加载插件
        self.plugin_loader.load_all_plugins()
        
        # 注册内置插件
        self._register_builtin_plugins()
        
        # 配置插件
        self._configure_plugins()
        
        logger.info("插件初始化完成")
    
    def _register_builtin_plugins(self):
        """注册内置插件"""
        # 注册抓取器插件
        self.fetcher_plugins['NewsFetcher'] = NewsFetcher({})
        
        # 注册通知器插件
        self.notifier_plugins['FeishuNotifier'] = FeishuNotifier({})
        self.notifier_plugins['DingTalkNotifier'] = DingTalkNotifier({})
        self.notifier_plugins['WeWorkNotifier'] = WeWorkNotifier({})
        self.notifier_plugins['EmailNotifier'] = EmailNotifier({})
        
        # 注册渲染器插件
        self.renderer_plugins['HTMLRenderer'] = HTMLRenderer({})
        self.renderer_plugins['TextRenderer'] = TextRenderer({})
    
    def _configure_plugins(self):
        """配置插件"""
        logger = logging.getLogger(__name__)
        
        # 配置渲染器
        html_config = self.config_manager.get_html_report_config()
        if html_config.get('enabled'):
            self.renderer_plugins['HTMLRenderer'].configure(html_config)
        
        text_config = self.config_manager.get_text_report_config()
        if text_config.get('enabled'):
            self.renderer_plugins['TextRenderer'].configure(text_config)
        
        # 配置通知器
        notification_configs = self.config_manager.get_notification_configs()
        
        for platform, config in notification_configs.items():
            if config.get('enabled'):
                notifier_name = f"{platform.capitalize()}Notifier"
                if notifier_name in self.notifier_plugins:
                    success = self.notifier_plugins[notifier_name].configure(config)
                    if success:
                        logger.info(f"{notifier_name} 配置成功")
                    else:
                        logger.warning(f"{notifier_name} 配置失败")
    
    async def crawl_platforms(self) -> Dict[str, Any]:
        """抓取所有平台数据"""
        logger = logging.getLogger(__name__)
        logger.info("开始抓取平台数据...")
        
        all_data = {}
        platforms = self.config_manager.get_platforms()
        
        for platform_config in platforms:
            # 将字典转换为PlatformConfig对象
            if isinstance(platform_config, dict):
                platform_config = PlatformConfig(**platform_config)
            
            if not platform_config.enabled:
                continue
            
            logger.info(f"抓取平台: {platform_config.name}")
            
            # 选择合适的抓取器
            fetcher = self._get_suitable_fetcher(platform_config)
            if not fetcher:
                logger.warning(f"未找到合适的抓取器: {platform_config.type}")
                continue
            
            try:
                error_msg, platform_data = fetcher.fetch_data(platform_config)
                
                if error_msg:
                    logger.error(f"抓取失败 {platform_config.name}: {error_msg}")
                else:
                    all_data.update(platform_data)
                    logger.info(f"抓取成功 {platform_config.name}: {len(platform_data)} 条数据")
                    
            except Exception as e:
                logger.error(f"抓取异常 {platform_config.name}: {str(e)}")
        
        logger.info(f"数据抓取完成，总计: {len(all_data)} 条数据")
        return all_data
    
    def _get_suitable_fetcher(self, platform_config: PlatformConfig):
        """获取合适的抓取器"""
        # 优先使用专门的抓取器
        for fetcher_name, fetcher in self.fetcher_plugins.items():
            if hasattr(fetcher, 'supports_platform'):
                if fetcher.supports_platform(platform_config.type):
                    return fetcher
        
        # 默认使用新闻抓取器
        return self.fetcher_plugins.get('NewsFetcher')
    
    def analyze_data(self, crawl_data: Dict[str, Any]) -> ReportData:
        """分析数据"""
        logger = logging.getLogger(__name__)
        logger.info("开始数据分析...")
        
        # 获取配置
        frequency_words = self.config_manager.get_frequency_words()
        word_groups = self.config_manager.get_word_groups()
        filter_words = self.config_manager.get_filter_words()
        rank_threshold = self.config_manager.get_rank_threshold()
        
        # 执行分析
        stats, total_titles = self.analysis_pipeline.process_data(
            data_source=crawl_data,
            word_groups=word_groups,
            filter_words=filter_words,
            mode="daily"
        )
        
        # 准备报告数据
        report_data = self.analysis_pipeline.prepare_report_data(
            stats=stats,
            new_titles={},
            failed_ids=[],
            total_titles=total_titles,
            mode="daily"
        )
        
        logger.info(f"数据分析完成: {len(report_data.stats)} 个关键词, "
                   f"{report_data.total_new_count} 个新标题")
        
        return report_data
    
    def generate_reports(self, report_data: ReportData) -> Dict[str, str]:
        """生成报告"""
        logger = logging.getLogger(__name__)
        logger.info("开始生成报告...")
        
        reports = {}
        
        # 准备上下文数据
        context = self._prepare_report_context(report_data)
        logger.info(f"报告上下文数据: {context}")
        
        # 生成 HTML 报告
        html_config = self.config_manager.get_html_report_config()
        logger.info(f"HTML 报告配置: {html_config}")
        if html_config.get('enabled'):
            html_renderer = self.renderer_plugins.get('HTMLRenderer')
            logger.info(f"HTML 渲染器: {html_renderer}, 配置状态: {html_renderer._configured if html_renderer else 'None'}")
            if html_renderer and html_renderer._configured:
                filename = self._generate_filename(html_config.get('filename', 'report.html'))
                logger.info(f"生成 HTML 报告，文件名: {filename}")
                html_content = html_renderer.render('report', context, filename)
                reports['html'] = html_content
                logger.info(f"HTML 报告生成完成: {filename}")
            else:
                logger.warning("HTML 渲染器未配置或不可用")
        else:
            logger.warning("HTML 报告未启用")
        
        # 生成文本报告
        text_config = self.config_manager.get_text_report_config()
        if text_config.get('enabled'):
            text_renderer = self.renderer_plugins.get('TextRenderer')
            if text_renderer and text_renderer._configured:
                filename = self._generate_filename(text_config.get('filename', 'report.md'))
                text_content = text_renderer.render('report', context, filename)
                reports['text'] = text_content
                logger.info(f"文本报告生成完成: {filename}")
        
        return reports
    
    def _prepare_report_context(self, report_data: ReportData) -> Dict[str, Any]:
        """准备报告上下文"""
        beijing_time = get_beijing_time()
        
        return {
            'title': '趋势雷达分析报告',
            'subtitle': '实时热点监控与关键词分析',
            'timestamp': beijing_time.strftime('%Y-%m-%d %H:%M:%S'),
            'version': self.config_manager.get_version(),
            'total_titles': report_data.get_total_titles(),
            'new_titles_count': report_data.total_new_count,
            'word_stats': report_data.stats[:20],  # 前20个
            'new_titles': list(report_data.new_titles.values())[:20],  # 前20个
            'platforms': list(set(title.source_name for stat in report_data.stats for title in stat.titles))
        }
    
    def _generate_filename(self, template: str) -> str:
        """生成文件名"""
        timestamp = get_beijing_time().strftime('%Y%m%d_%H%M%S')
        return template.replace('{{ timestamp }}', timestamp)
    
    async def send_notifications(self, report_data: ReportData, reports: Dict[str, str]):
        """发送通知"""
        logger = logging.getLogger(__name__)
        logger.info("开始发送通知...")
        
        # 准备通知内容
        title = f"趋势雷达 - {get_beijing_time().strftime('%Y-%m-%d %H:%M')}"
        content = self._prepare_notification_content(report_data)
        
        # 发送各个平台的通知
        notification_configs = self.config_manager.get_notification_configs()
        
        for platform, config in notification_configs.items():
            if not config.get('enabled'):
                continue
            
            notifier_name = f"{platform.capitalize()}Notifier"
            notifier = self.notifier_plugins.get(notifier_name)
            
            if not notifier or not notifier._configured:
                continue
            
            try:
                success = notifier.send_notification(title, content)
                if success:
                    logger.info(f"{notifier_name} 通知发送成功")
                else:
                    logger.warning(f"{notifier_name} 通知发送失败")
                    
            except Exception as e:
                logger.error(f"{notifier_name} 通知发送异常: {str(e)}")
    
    def _prepare_notification_content(self, report_data: ReportData) -> str:
        """准备通知内容"""
        lines = []
        lines.append(f"📊 趋势雷达报告 {get_beijing_time().strftime('%m月%d日 %H:%M')}")
        lines.append(f"总标题数: {report_data.get_total_titles()}")
        lines.append(f"新标题数: {report_data.total_new_count}")
        lines.append(f"关键词统计: {len(report_data.stats)}")
        
        # 前5个热门关键词
        if report_data.stats:
            lines.append("\n🔥 热门关键词:")
            for stat in report_data.stats[:5]:
                lines.append(f"• {stat.word}: {stat.count}次")
        
        # 前3个新标题
        if report_data.new_titles:
            lines.append("\n🆕 新标题:")
            for source_titles in list(report_data.new_titles.values())[:3]:
                for title in source_titles[:1]:
                    lines.append(f"• {title.title}")
        
        return "\n".join(lines)
    
    async def run(self, mode: str = "incremental"):
        """运行趋势雷达"""
        logger = logging.getLogger(__name__)
        logger.info(f"开始运行 TrendRadar (模式: {mode})")
        
        try:
            # 初始化插件
            self.initialize_plugins()
            
            # 检查是否是首次抓取（强制运行模式）
            if mode == "incremental" and not is_first_crawl_today():
                logger.info("今日已抓取过，但继续运行以生成报告")
            
            # 抓取数据
            crawl_data = await self.crawl_platforms()
            
            if not crawl_data:
                logger.warning("未获取到任何数据")
                return
            
            # 保存抓取记录
            save_crawl_record()
            
            # 分析数据
            report_data = self.analyze_data(crawl_data)
            
            # 生成报告
            reports = self.generate_reports(report_data)
            
            # 发送通知
            await self.send_notifications(report_data, reports)
            
            logger.info("TrendRadar 运行完成")
            
        except Exception as e:
            logger.error(f"TrendRadar 运行失败: {str(e)}")
            raise


async def main():
    """主函数"""
    # 创建趋势雷达实例
    trend_radar = TrendRadar()
    
    # 运行
    await trend_radar.run(mode="incremental")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
