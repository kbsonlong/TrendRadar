# TrendRadar 重构方案

## 1. 重构目标

将现有的单体架构重构为模块化、插件化的架构，提高代码可维护性和扩展性：
- 清晰的目录结构，分离关注点
- 使用 Jinja2 模板引擎渲染 HTML 报告
- 平台推送功能插件化
- 数据抓取功能插件化
- 保持现有功能完整性

## 2. 新的目录结构

```
TrendRadar/
├── src/                          # 源代码目录
│   ├── core/                     # 核心模块
│   │   ├── __init__.py
│   │   ├── analyzer.py          # 核心分析器
│   │   ├── config.py            # 配置管理
│   │   ├── data_models.py       # 数据模型
│   │   ├── pipeline.py          # 分析流水线
│   │   └── utils.py             # 工具函数
│   ├── plugins/                  # 插件目录
│   │   ├── __init__.py
│   │   ├── base.py              # 插件基类
│   │   ├── fetchers/            # 数据抓取插件
│   │   │   ├── __init__.py
│   │   │   ├── base_fetcher.py  # 抓取器基类
│   │   │   ├── news_fetcher.py  # 新闻抓取器
│   │   │   └── ...              # 其他抓取器
│   │   ├── notifiers/           # 通知插件
│   │   │   ├── __init__.py
│   │   │   ├── base_notifier.py # 通知器基类
│   │   │   ├── feishu.py        # 飞书通知
│   │   │   ├── dingtalk.py      # 钉钉通知
│   │   │   ├── wework.py        # 企业微信
│   │   │   ├── telegram.py      # Telegram
│   │   │   ├── email.py         # 邮件通知
│   │   │   └── ntfy.py         # ntfy通知
│   │   └── renderers/           # 内容渲染插件
│   │       ├── __init__.py
│   │       ├── base_renderer.py # 渲染器基类
│   │       ├── html_renderer.py # HTML渲染
│   │       └── text_renderer.py # 文本渲染
│   ├── templates/               # 模板目录
│   │   ├── __init__.py
│   │   ├── html/                # HTML模板
│   │   │   ├── base.html        # 基础模板
│   │   │   ├── report.html      # 报告模板
│   │   │   └── styles.css       # 样式文件
│   │   └── text/                # 文本模板
│   │       ├── feishu.txt        # 飞书消息模板
│   │       ├── dingtalk.txt     # 钉钉消息模板
│   │       └── ...              # 其他平台模板
│   └── main.py                   # 程序入口
├── config/                       # 配置文件
│   ├── config.yaml              # 主配置
│   └── frequency_words.txt      # 频率词配置
├── output/                       # 输出目录
│   ├── html/                    # HTML报告
│   └── logs/                    # 日志文件
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── test_plugins.py          # 插件测试
│   └── test_core.py             # 核心测试
├── docker/                       # Docker相关
├── docs/                         # 文档
├── requirements.txt            # 依赖
├── README.md                    # 项目说明
└── setup.py                     # 安装脚本
```

## 3. 核心模块设计

### 3.1 配置管理 (core/config.py)

```python
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/config.yaml")
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            value = value.get(k)
            if value is None:
                return default
        return value
    
    def get_platforms(self) -> list:
        """获取平台配置"""
        return self.get('PLATFORMS', [])
    
    def get_notifier_config(self, notifier_type: str) -> Dict[str, Any]:
        """获取通知器配置"""
        return self.get(f'{notifier_type.upper()}_CONFIG', {})
```

### 3.2 数据模型 (core/data_models.py)

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class TitleData:
    """标题数据模型"""
    title: str
    source_name: str
    is_new: bool = False
    ranks: List[int] = None
    rank_display: str = ""
    time_display: str = ""
    count: int = 1
    url: str = ""
    mobile_url: str = ""
    
    def __post_init__(self):
        if self.ranks is None:
            self.ranks = []

@dataclass
class WordStat:
    """词频统计模型"""
    word: str
    count: int
    titles: List[TitleData]
    
@dataclass
class ReportData:
    """报告数据模型"""
    stats: List[WordStat]
    new_titles: Dict[str, List[TitleData]]
    failed_ids: List[str]
    total_new_count: int
    update_info: Optional[Dict[str, Any]] = None
    
@dataclass
class PlatformConfig:
    """平台配置模型"""
    id: str
    name: str
    url: str
    type: str = "news"
    enabled: bool = True
```

### 3.3 分析流水线 (core/pipeline.py)

```python
from typing import List, Dict, Any, Optional, Tuple
from .data_models import ReportData, WordStat, TitleData
from .utils import clean_title, get_beijing_time

class AnalysisPipeline:
    """分析流水线"""
    
    def __init__(self, config):
        self.config = config
        self.rank_threshold = config.get('RANK_THRESHOLD', 50)
    
    def process_data(
        self,
        data_source: Dict[str, Any],
        word_groups: List[Dict[str, Any]],
        filter_words: List[str],
        new_titles: Optional[Dict[str, List[TitleData]]] = None,
        mode: str = "daily"
    ) -> Tuple[List[WordStat], int]:
        """处理数据并生成统计结果"""
        
        # 词频统计
        stats = self._count_word_frequency(
            data_source, word_groups, filter_words, new_titles, mode
        )
        
        # 计算总标题数
        total_titles = sum(len(stat.titles) for stat in stats)
        
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
        # 实现词频统计逻辑
        stats = []
        
        for word_group in word_groups:
            word = word_group['word']
            required_words = word_group.get('required_words', [])
            frequency_words = word_group.get('frequency_words', [])
            
            # 匹配标题
            matched_titles = self._match_titles(
                data_source, word, required_words, frequency_words, filter_words, mode
            )
            
            if matched_titles:
                stat = WordStat(
                    word=word,
                    count=len(matched_titles),
                    titles=matched_titles
                )
                stats.append(stat)
        
        # 按数量排序
        stats.sort(key=lambda x: x.count, reverse=True)
        
        return stats
    
    def _match_titles(
        self,
        data_source: Dict[str, Any],
        word: str,
        required_words: List[str],
        frequency_words: List[str],
        filter_words: List[str],
        mode: str
    ) -> List[TitleData]:
        """匹配标题"""
        matched_titles = []
        
        for source_id, titles_data in data_source.items():
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
        # 实现匹配逻辑
        title_lower = title.lower()
        
        # 检查过滤词
        for filter_word in filter_words:
            if filter_word.lower() in title_lower:
                return False
        
        # 检查必需词
        for required_word in required_words:
            if required_word.lower() not in title_lower:
                return False
        
        # 检查频率词
        for frequency_word in frequency_words:
            if frequency_word.lower() in title_lower:
                return True
        
        # 检查主词
        return word.lower() in title_lower
    
    def _is_new_title(self, title: str, source_id: str, new_titles: Optional[Dict[str, List[TitleData]]]) -> bool:
        """检查是否为新增标题"""
        if not new_titles or source_id not in new_titles:
            return False
        
        return any(t.title == title for t in new_titles[source_id])
    
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
        except:
            return time_info
```

## 4. 插件接口定义

### 4.1 插件基类 (plugins/base.py)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BasePlugin(ABC):
    """插件基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def get_name(self) -> str:
        """获取插件名称"""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """获取插件版本"""
        pass
    
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self.enabled
```

### 4.2 数据抓取器接口 (plugins/fetchers/base_fetcher.py)

```python
from abc import abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from ..base import BasePlugin
from src.core.data_models import PlatformConfig

class BaseFetcher(BasePlugin):
    """数据抓取器基类"""
    
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
```

### 4.3 通知器接口 (plugins/notifiers/base_notifier.py)

```python
from abc import abstractmethod
from typing import Dict, Any, Optional
from ..base import BasePlugin
from src.core.data_models import ReportData

class BaseNotifier(BasePlugin):
    """通知器基类"""
    
    @abstractmethod
    def send_notification(
        self,
        report_data: ReportData,
        report_type: str,
        update_info: Optional[Dict[str, Any]] = None,
        mode: str = "daily"
    ) -> bool:
        """
        发送通知
        
        Args:
            report_data: 报告数据
            report_type: 报告类型
            update_info: 更新信息
            mode: 运行模式
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    def supports_batching(self) -> bool:
        """是否支持分批发送"""
        return False
    
    @abstractmethod
    def get_max_batch_size(self) -> int:
        """获取最大批次大小（字节）"""
        return 4000
```

### 4.4 渲染器接口 (plugins/renderers/base_renderer.py)

```python
from abc import abstractmethod
from typing import Dict, Any, Optional
from ..base import BasePlugin
from src.core.data_models import ReportData

class BaseRenderer(BasePlugin):
    """渲染器基类"""
    
    @abstractmethod
    def render(
        self,
        report_data: ReportData,
        report_type: str,
        update_info: Optional[Dict[str, Any]] = None,
        mode: str = "daily"
    ) -> str:
        """
        渲染内容
        
        Args:
            report_data: 报告数据
            report_type: 报告类型
            update_info: 更新信息
            mode: 运行模式
            
        Returns:
            渲染后的内容
        """
        pass
    
    @abstractmethod
    def get_content_type(self) -> str:
        """获取内容类型"""
        pass
```

## 5. 模板文件结构

### 5.1 HTML 模板 (templates/html/)

**base.html**
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}TrendRadar 热点分析报告{% endblock %}</title>
    <style>
        {% include 'styles.css' %}
    </style>
</head>
<body>
    <div class="container">
        {% block header %}
        <header>
            <h1>TrendRadar 热点分析报告</h1>
            <div class="meta">
                <span>报告类型: {{ report_type }}</span>
                <span>生成时间: {{ generation_time }}</span>
                {% if update_info %}
                <span class="update-info">新版本可用: {{ update_info.remote_version }}</span>
                {% endif %}
            </div>
        </header>
        {% endblock %}
        
        <main>
            {% block content %}{% endblock %}
        </main>
        
        {% block footer %}
        <footer>
            <p>Generated by TrendRadar v{{ version }}</p>
        </footer>
        {% endblock %}
    </div>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

**report.html**
```html
{% extends 'base.html' %}

{% block content %}
<div class="summary">
    <h2>统计摘要</h2>
    <div class="stats-grid">
        <div class="stat-item">
            <span class="label">总新闻数:</span>
            <span class="value">{{ total_titles }}</span>
        </div>
        <div class="stat-item">
            <span class="label">热点词汇数:</span>
            <span class="value">{{ stats|length }}</span>
        </div>
        {% if total_new_count > 0 %}
        <div class="stat-item">
            <span class="label">新增新闻:</span>
            <span class="value">{{ total_new_count }}</span>
        </div>
        {% endif %}
    </div>
</div>

{% if stats %}
<div class="word-stats">
    <h2>热点词汇统计</h2>
    {% for stat in stats %}
    <div class="word-stat">
        <div class="word-header">
            <h3>{{ stat.word }}</h3>
            <span class="count">{{ stat.count }} 条</span>
            {% if stat.count >= 10 %}
            <span class="badge hot">🔥</span>
            {% elif stat.count >= 5 %}
            <span class="badge trending">📈</span>
            {% else %}
            <span class="badge normal">📌</span>
            {% endif %}
        </div>
        
        <div class="titles">
            {% for title in stat.titles %}
            <div class="title-item {% if title.is_new %}new{% endif %}">
                <div class="title-header">
                    <span class="source">{{ title.source_name }}</span>
                    {% if title.rank_display %}
                    <span class="rank">{{ title.rank_display }}</span>
                    {% endif %}
                    {% if title.time_display %}
                    <span class="time">{{ title.time_display }}</span>
                    {% endif %}
                </div>
                <div class="title-content">
                    {{ title.title }}
                    {% if title.is_new %}<span class="new-badge">新</span>{% endif %}
                </div>
                {% if title.url %}
                <div class="title-actions">
                    <a href="{{ title.url }}" target="_blank" class="link">查看原文</a>
                    {% if title.mobile_url %}
                    <a href="{{ title.mobile_url }}" target="_blank" class="link mobile">手机版</a>
                    {% endif %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>
{% endif %}

{% if new_titles %}
<div class="new-titles">
    <h2>新增热点新闻</h2>
    {% for source_name, titles in new_titles.items() %}
    <div class="source-group">
        <h3>{{ source_name }} ({{ titles|length }} 条)</h3>
        {% for title in titles %}
        <div class="title-item new">
            <div class="title-content">{{ title.title }}</div>
            {% if title.url %}
            <div class="title-actions">
                <a href="{{ title.url }}" target="_blank" class="link">查看原文</a>
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endfor %}
</div>
{% endif %}

{% if failed_ids %}
<div class="failed-platforms">
    <h2>数据获取失败的平台</h2>
    <div class="failed-list">
        {% for failed_id in failed_ids %}
        <div class="failed-item">{{ failed_id }}</div>
        {% endfor %}
    </div>
</div>
{% endif %}

<div class="save-actions">
    <button id="saveAsImage" class="save-button">保存为图片</button>
    <div class="save-options" style="display: none;">
        <label>
            <input type="radio" name="saveMode" value="full" checked> 完整保存
        </label>
        <label>
            <input type="radio" name="saveMode" value="split"> 分段保存
        </label>
        <button id="confirmSave" class="save-button">确认保存</button>
        <button id="cancelSave" class="cancel-button">取消</button>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script>
// 保存图片功能
(function() {
    let saveMode = 'full';
    
    document.getElementById('saveAsImage').addEventListener('click', function() {
        document.querySelector('.save-options').style.display = 'block';
        this.style.display = 'none';
    });
    
    document.getElementById('cancelSave').addEventListener('click', function() {
        document.querySelector('.save-options').style.display = 'none';
        document.getElementById('saveAsImage').style.display = 'block';
    });
    
    document.getElementById('confirmSave').addEventListener('click', async function() {
        saveMode = document.querySelector('input[name="saveMode"]:checked').value;
        await saveAsImage(saveMode);
        document.querySelector('.save-options').style.display = 'none';
        document.getElementById('saveAsImage').style.display = 'block';
    });
    
    async function saveAsImage(mode) {
        const container = document.querySelector('.container');
        const button = document.getElementById('confirmSave');
        const originalText = button.textContent;
        
        button.textContent = '生成中...';
        button.disabled = true;
        
        try {
            if (mode === 'full') {
                await saveFullImage();
            } else {
                await saveSplitImages();
            }
            
            button.textContent = '保存成功!';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        } catch (error) {
            console.error('保存失败:', error);
            button.textContent = '保存失败';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        }
    }
    
    async function saveFullImage() {
        const canvas = await html2canvas(document.querySelector('.container'), {
            backgroundColor: '#ffffff',
            scale: 2,
            useCORS: true,
            allowTaint: false,
            imageTimeout: 10000,
            logging: false
        });
        
        const link = document.createElement('a');
        link.download = `TrendRadar_{{ generation_time.replace(' ', '_').replace(':', '-') }}.png`;
        link.href = canvas.toDataURL('image/png', 1.0);
        link.click();
    }
    
    async function saveSplitImages() {
        // 分段保存逻辑
        const sections = document.querySelectorAll('.word-stat, .new-titles, .failed-platforms');
        const baseFilename = `TrendRadar_{{ generation_time.replace(' ', '_').replace(':', '-') }}`;
        
        for (let i = 0; i < sections.length; i++) {
            const section = sections[i];
            const canvas = await html2canvas(section, {
                backgroundColor: '#ffffff',
                scale: 2,
                useCORS: true,
                allowTaint: false,
                imageTimeout: 10000,
                logging: false
            });
            
            const link = document.createElement('a');
            link.download = `${baseFilename}_part${i + 1}.png`;
            link.href = canvas.toDataURL('image/png', 1.0);
            link.click();
            
            // 延迟一下避免浏览器阻止多个下载
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
})();
</script>
{% endblock %}
```

**styles.css**
```css
/* 基础样式 */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f5f5f5;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background-color: white;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
}

/* 头部 */
header {
    text-align: center;
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 2px solid #e0e0e0;
}

header h1 {
    color: #2c3e50;
    margin-bottom: 10px;
}

.meta {
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
}

.meta span {
    color: #666;
}

.update-info {
    color: #e74c3c;
    font-weight: bold;
}

/* 统计摘要 */
.summary {
    margin-bottom: 30px;
}

.summary h2 {
    color: #2c3e50;
    margin-bottom: 15px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.stat-item {
    background-color: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.stat-item .label {
    color: #666;
}

.stat-item .value {
    font-size: 24px;
    font-weight: bold;
    color: #3498db;
}

/* 词频统计 */
.word-stats {
    margin-bottom: 30px;
}

.word-stats h2 {
    color: #2c3e50;
    margin-bottom: 20px;
}

.word-stat {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
}

.word-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 15px;
}

.word-header h3 {
    color: #2c3e50;
    font-size: 20px;
}

.word-header .count {
    color: #666;
    font-size: 16px;
}

.badge {
    font-size: 20px;
}

.badge.hot {
    color: #e74c3c;
}

.badge.trending {
    color: #f39c12;
}

.badge.normal {
    color: #95a5a6;
}

.titles {
    margin-top: 15px;
}

.title-item {
    background-color: white;
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 10px;
    border-left: 4px solid #3498db;
}

.title-item.new {
    border-left-color: #27ae60;
    background-color: #f0fff4;
}

.title-header {
    display: flex;
    gap: 15px;
    margin-bottom: 10px;
    font-size: 14px;
    color: #666;
}

.title-header .source {
    font-weight: bold;
    color: #2c3e50;
}

.title-header .rank {
    color: #e74c3c;
}

.title-header .time {
    color: #95a5a6;
}

.title-content {
    font-size: 16px;
    line-height: 1.5;
    margin-bottom: 10px;
}

.new-badge {
    display: inline-block;
    background-color: #27ae60;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    margin-left: 5px;
}

.title-actions {
    display: flex;
    gap: 10px;
}

.link {
    color: #3498db;
    text-decoration: none;
    font-size: 14px;
}

.link:hover {
    text-decoration: underline;
}

.link.mobile {
    color: #95a5a6;
}

/* 新增新闻 */
.new-titles {
    margin-bottom: 30px;
}

.new-titles h2 {
    color: #2c3e50;
    margin-bottom: 20px;
}

.source-group {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
}

.source-group h3 {
    color: #2c3e50;
    margin-bottom: 15px;
}

/* 失败平台 */
.failed-platforms {
    margin-bottom: 30px;
}

.failed-platforms h2 {
    color: #e74c3c;
    margin-bottom: 15px;
}

.failed-list {
    background-color: #fdf2f2;
    border-radius: 8px;
    padding: 15px;
}

.failed-item {
    color: #e74c3c;
    padding: 5px 0;
    border-bottom: 1px solid #fbe3e3;
}

.failed-item:last-child {
    border-bottom: none;
}

/* 保存操作 */
.save-actions {
    text-align: center;
    margin-top: 30px;
    padding-top: 20px;
    border-top: 2px solid #e0e0e0;
}

.save-button, .cancel-button {
    background-color: #3498db;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    margin: 0 5px;
}

.save-button:hover {
    background-color: #2980b9;
}

.cancel-button {
    background-color: #95a5a6;
}

.cancel-button:hover {
    background-color: #7f8c8d;
}

.save-options {
    margin-top: 15px;
}

.save-options label {
    display: inline-block;
    margin: 0 10px;
    cursor: pointer;
}

.save-options input[type="radio"] {
    margin-right: 5px;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    .meta {
        flex-direction: column;
        gap: 10px;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .word-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 5px;
    }
    
    .title-header {
        flex-direction: column;
        gap: 5px;
    }
    
    .title-actions {
        flex-direction: column;
        gap: 5px;
    }
}

/* 打印样式 */
@media print {
    .save-actions {
        display: none;
    }
    
    body {
        background-color: white;
    }
    
    .container {
        box-shadow: none;
    }
}
```

### 5.2 文本模板 (templates/text/)

**feishu.txt**
```
{% if stats %}
📊 **热点词汇统计**

{% for stat in stats %}
{% set sequence_display = "[{}]".format(loop.index) %}
{% if stat.count >= 10 %}
🔥 {{ sequence_display }} **{{ stat.word }}** : <font color='red'>{{ stat.count }}</font> 条

{% elif stat.count >= 5 %}
📈 {{ sequence_display }} **{{ stat.word }}** : <font color='orange'>{{ stat.count }}</font> 条

{% else %}
📌 {{ sequence_display }} **{{ stat.word }}** : {{ stat.count }} 条

{% endif %}
{% for title in stat.titles %}
  {{ loop.index }}. {{ render_title('feishu', title, show_source=true) }}
{% endfor %}

{% if not loop.last %}
{{ message_separator }}

{% endif %}
{% endfor %}
{% else %}
📭 {% if mode == 'incremental' %}增量模式下暂无新增匹配的热点词汇{% elif mode == 'current' %}当前榜单模式下暂无匹配的热点词汇{% else %}暂无匹配的热点词汇{% endif %}

{% endif %}

{% if new_titles %}
{% if stats %}
{{ message_separator }}

{% endif %}
🆕 **本次新增热点新闻** (共 {{ total_new_count }} 条)

{% for source_name, titles in new_titles.items() %}
**{{ source_name }}** ({{ titles|length }} 条):
{% for title in titles %}
  {{ loop.index }}. {{ render_title('feishu', title, show_source=false) }}
{% endfor %}

{% endfor %}
{% endif %}

{% if failed_ids %}
{% if stats or new_titles %}
{{ message_separator }}

{% endif %}
⚠️ **数据获取失败的平台：**

{% for failed_id in failed_ids %}
  • <font color='red'>{{ failed_id }}</font>
{% endfor %}
{% endif %}

更新时间：{{ generation_time }}
{% if update_info %}
TrendRadar 发现新版本 {{ update_info.remote_version }}，当前 {{ update_info.current_version }}
{% endif %}
```

## 6. 重构实施步骤

### 第一阶段：基础架构搭建（1-2天）
1. 创建新的目录结构
2. 实现配置管理模块
3. 定义数据模型
4. 创建插件基类和接口

### 第二阶段：核心功能迁移（2-3天）
1. 迁移词频统计逻辑到分析流水线
2. 实现数据抓取插件架构
3. 创建HTML模板和渲染器
4. 迁移通知功能到插件架构

### 第三阶段：插件实现（2-3天）
1. 实现各个平台的抓取器插件
2. 实现各个平台的通知器插件
3. 实现文本渲染器插件
4. 添加插件管理和加载机制

### 第四阶段：测试和优化（1-2天）
1. 编写单元测试
2. 集成测试
3. 性能优化
4. 文档编写

### 第五阶段：部署和迁移（1天）
1. 更新Docker配置
2. 更新CI/CD配置
3. 数据迁移
4. 生产环境部署

## 7. 技术选型

- **模板引擎**: Jinja2
- **插件架构**: 基于抽象基类的插件系统
- **配置管理**: YAML + 环境变量
- **日志**: Python logging
- **测试**: pytest
- **代码质量**: black, flake8, mypy

## 8. 优势

1. **模块化**: 各功能模块独立，便于维护和测试
2. **可扩展**: 通过插件机制轻松添加新平台
3. **可配置**: 灵活的配置管理
4. **可测试**: 清晰的接口定义便于单元测试
5. **可维护**: 代码结构清晰，职责分离
6. **模板化**: 使用专业模板引擎，提高渲染效率

## 9. 风险和控制

1. **功能兼容性**: 确保重构后功能完全一致
2. **性能影响**: 监控重构后的性能表现
3. **配置迁移**: 确保现有配置能够平滑迁移
4. **插件稳定性**: 充分