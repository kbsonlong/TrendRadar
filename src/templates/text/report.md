# {{ title }}

{{ subtitle }}

**生成时间**: {{ timestamp }}

---

## 📊 统计概览

- **总标题数**: {{ total_titles }}
- **新标题数**: {{ new_titles_count }}
- **关键词统计**: {{ word_stats|length }}
- **监控平台**: {{ platforms|length }}

### 关键词详细统计

{% if word_stats %}
| 关键词 | 出现次数 | 最高排名 | 来源平台 | 首次出现 |
|--------|----------|----------|----------|----------|
{% for word, stat in word_stats %}
| {{ word }} | {{ stat.count }} | {% if stat.min_rank %}#{{ stat.min_rank }}{% else %}-{% endif %} | {{ stat.source_names|join(", ") }} | {{ stat.first_time|format_time }} |
{% endfor %}
{% else %}
暂无关键词统计数据
{% endif %}

---

## 🆕 新发现标题

{% if new_titles %}
{% for title in new_titles %}
### {{ title.text }}
- **来源**: {{ title.source_name }}
- **时间**: {{ title.time_info }}
- **状态**: 🆕 新发现

---
{% endfor %}
{% else %}
暂无新发现标题
{% endif %}

---

*由 TrendRadar v{{ version }} 自动生成*