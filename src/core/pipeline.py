"""
分析流水线模块
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import re

from .data_models import ReportData, WordStat, TitleData
from .utils import clean_title, get_beijing_time, html_escape

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """分析流水线"""
    
    def __init__(self, config):
        self.config = config
        self.rank_threshold = config.get('RANK_THRESHOLD', 50)
        self.batch_send_interval = config.get('BATCH_SEND_INTERVAL', 2)
        logger.info(f"初始化分析流水线，排名阈值: {self.rank_threshold}")
    
    def process_data(
        self,
        data_source: Dict[str, Any],
        word_groups: List[Dict[str, Any]],
        filter_words: List[str],
        new_titles: Optional[Dict[str, List[TitleData]]] = None,
        mode: str = "daily"
    ) -> Tuple[List[WordStat], int]:
        """处理数据并生成统计结果"""
        logger.info(f"开始处理数据，模式: {mode}, 词组数量: {len(word_groups)}")
        
        # 词频统计
        stats = self._count_word_frequency(
            data_source, word_groups, filter_words, new_titles, mode
        )
        
        # 计算总标题数
        total_titles = sum(len(stat.titles) for stat in stats)
        
        logger.info(f"数据处理完成，热点词汇: {len(stats)}, 总标题数: {total_titles}")
        return stats, total_titles
    
    def _count_word_frequency(
        self,
        data_source: Dict[str, Any],
        word_groups: List[Dict[str, Any]],
        filter_words: List[str],
        new_titles: Optional[Dict[str, List[TitleData]]] = None,
        mode: str = "daily"
    ) -> List[WordStat]:
        """统计词频"""
        stats = []
        
        for word_group in word_groups:
            word = word_group['word']
            required_words = word_group.get('required_words', [])
            frequency_words = word_group.get('frequency_words', [])
            
            logger.debug(f"处理词组: {word}, 必需词: {required_words}, 频率词: {frequency_words}")
            
            # 匹配标题
            matched_titles = self._match_titles(
                data_source, word, required_words, frequency_words, filter_words, mode, new_titles
            )
            
            if matched_titles:
                stat = WordStat(
                    word=word,
                    count=len(matched_titles),
                    titles=matched_titles
                )
                stats.append(stat)
                logger.debug(f"词组 '{word}' 匹配到 {len(matched_titles)} 个标题")
        
        # 按数量排序
        stats.sort(key=lambda x: x.count, reverse=True)
        
        logger.info(f"词频统计完成，共 {len(stats)} 个热点词汇")
        return stats
    
    def _match_titles(
        self,
        data_source: Dict[str, Any],
        word: str,
        required_words: List[str],
        frequency_words: List[str],
        filter_words: List[str],
        mode: str,
        new_titles: Optional[Dict[str, List[TitleData]]] = None
    ) -> List[TitleData]:
        """匹配标题"""
        matched_titles = []
        
        for source_id, titles_data in data_source.items():
            logger.debug(f"处理数据源: {source_id}, 标题数量: {len(titles_data)}")
            
            for title, title_info in titles_data.items():
                # 清洗标题
                clean_title_text = clean_title(title)
                
                # 检查是否匹配
                if self._is_title_match(
                    clean_title_text, word, required_words, frequency_words, filter_words
                ):
                    # 创建标题数据
                    title_data = TitleData(
                        title=title,
                        source_name=title_info.get('source_name', source_id),
                        is_new=self._is_new_title(title, source_id, new_titles),
                        ranks=title_info.get('ranks', []),
                        rank_display=self._format_rank_display(title_info.get('ranks', [])),
                        time_display=self._format_time_display(title_info.get('time_info', '')),
                        count=title_info.get('count', 1),
                        url=title_info.get('url', ''),
                        mobile_url=title_info.get('mobile_url', '')
                    )
                    
                    matched_titles.append(title_data)
                    logger.debug(f"标题匹配成功: {title[:50]}...")
        
        logger.debug(f"词组 '{word}' 匹配完成，共 {len(matched_titles)} 个标题")
        return matched_titles
    
    def _is_title_match(
        self,
        title: str,
        word: str,
        required_words: List[str],
        frequency_words: List[str],
        filter_words: List[str]
    ) -> bool:
        """检查标题是否匹配"""
        title_lower = title.lower()
        
        # 检查过滤词
        for filter_word in filter_words:
            if filter_word.lower() in title_lower:
                logger.debug(f"标题被过滤词 '{filter_word}' 过滤")
                return False
        
        # 检查必需词
        for required_word in required_words:
            if required_word.lower() not in title_lower:
                logger.debug(f"标题缺少必需词 '{required_word}'")
                return False
        
        # 检查频率词
        for frequency_word in frequency_words:
            if frequency_word.lower() in title_lower:
                logger.debug(f"标题包含频率词 '{frequency_word}'")
                return True
        
        # 检查主词
        word_match = word.lower() in title_lower
        if word_match:
            logger.debug(f"标题包含主词 '{word}'")
        
        return word_match
    
    def _is_new_title(self, title: str, source_id: str, new_titles: Optional[Dict[str, List[TitleData]]]) -> bool:
        """检查是否为新增标题"""
        if not new_titles or source_id not in new_titles:
            return False
        
        is_new = any(t.title == title for t in new_titles[source_id])
        if is_new:
            logger.debug(f"标题 '{title[:30]}...' 是新标题")
        
        return is_new
    
    def _format_rank_display(self, ranks: List[int]) -> str:
        """格式化排名显示"""
        if not ranks:
            return ""
        
        ranks_sorted = sorted(ranks)
        if len(ranks_sorted) == 1:
            return f"第{ranks_sorted[0]}名"
        else:
            return f"第{ranks_sorted[0]}名"
    
    def _format_time_display(self, time_info: str) -> str:
        """格式化时间显示"""
        if not time_info:
            return ""
        
        try:
            # 解析时间并格式化
            dt = datetime.fromisoformat(time_info)
            return dt.strftime("%m月%d日 %H:%M")
        except Exception as e:
            logger.debug(f"时间格式化失败: {e}, 原值: {time_info}")
            return time_info
    
    def prepare_report_data(
        self,
        stats: List[WordStat],
        new_titles: Dict[str, List[TitleData]],
        failed_ids: List[str],
        total_titles: int,
        update_info: Optional[Dict[str, Any]] = None,
        mode: str = "daily"
    ) -> ReportData:
        """准备报告数据"""
        logger.info(f"准备报告数据，模式: {mode}")
        
        report_data = ReportData(
            stats=stats,
            new_titles=new_titles,
            failed_ids=failed_ids,
            total_new_count=sum(len(titles) for titles in new_titles.values()),
            update_info=update_info
        )
        
        logger.info(f"报告数据准备完成，热点词汇: {len(stats)}, 新增标题: {report_data.total_new_count}, 失败平台: {len(failed_ids)}")
        return report_data