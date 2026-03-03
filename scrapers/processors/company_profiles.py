"""
公司档案管理器

从每周采集数据中提取公司相关事件，累积到公司时间线。
为每家追踪公司维护一个持久化的事件列表。
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict

from sources.base import ScrapedItem

logger = logging.getLogger(__name__)

# 追踪的公司列表及其别名
TRACKED_COMPANIES = {
    "ReelShort": {
        "aliases": ["ReelShort", "Crazy Maple Studio", "枫叶互动"],
        "category": "出海平台",
        "description": "北美最大短剧平台，Crazy Maple Studio旗下",
        "stock": None,
    },
    "DramaBox": {
        "aliases": ["DramaBox", "Storymatrix"],
        "category": "出海平台",
        "description": "出海短剧平台，下载量增长迅速",
        "stock": None,
    },
    "ShortMax": {
        "aliases": ["ShortMax"],
        "category": "出海平台",
        "description": "出海短剧平台",
        "stock": None,
    },
    "GoodShort": {
        "aliases": ["GoodShort"],
        "category": "出海平台",
        "description": "出海短剧平台，评分最高",
        "stock": None,
    },
    "中文在线": {
        "aliases": ["中文在线"],
        "category": "上市公司",
        "description": "A股上市（300364），短剧业务重要布局者",
        "stock": "300364.SZ",
    },
    "点众科技": {
        "aliases": ["点众科技", "点众"],
        "category": "行业龙头",
        "description": "短剧行业头部公司",
        "stock": None,
    },
    "九州文化": {
        "aliases": ["九州文化", "九州"],
        "category": "头部公司",
        "description": "短剧制作发行头部公司",
        "stock": None,
    },
    "红果短剧": {
        "aliases": ["红果短剧", "红果"],
        "category": "国内平台",
        "description": "字节跳动旗下，国内DAU最高的短剧平台",
        "parent": "字节跳动",
    },
    "花生短剧": {
        "aliases": ["花生短剧", "花生"],
        "category": "国内平台",
        "description": "点众科技旗下短剧平台",
        "parent": "点众科技",
    },
    "容量文化": {
        "aliases": ["容量文化"],
        "category": "头部公司",
        "description": "短剧制作公司",
        "stock": None,
    },
}


class CompanyProfileManager:
    def __init__(self, data_path: str, content_dir: str):
        """
        data_path: 公司时间线数据文件，如 hugo-site/data/company_timelines.json
        content_dir: Hugo content目录，如 hugo-site/content/companies/
        """
        self.data_path = data_path
        self.content_dir = content_dir
        self.timelines: Dict[str, List[Dict]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.timelines = json.load(f)
            total = sum(len(v) for v in self.timelines.values())
            logger.info(f"[company] 加载 {len(self.timelines)} 家公司, {total} 条事件")

    def _save(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.timelines, f, ensure_ascii=False, indent=2)

    def update_from_items(self, items: List[ScrapedItem], week_id: str):
        """从采集数据中提取公司相关事件，追加到时间线"""
        new_events = 0

        for company_name, info in TRACKED_COMPANIES.items():
            aliases = info["aliases"]

            for item in items:
                if item.source == "appstore":
                    continue
                text = f"{item.title} {item.summary}"

                if not any(alias in text for alias in aliases):
                    continue

                event = {
                    "week_id": week_id,
                    "date": item.published_at[:10] if item.published_at else week_id,
                    "title": item.title,
                    "source": item.author,
                    "platform": item.source,
                    "url": item.url,
                    "summary": item.summary[:150] if item.summary else "",
                    "score": item.extra.get("score", 0),
                }

                if company_name not in self.timelines:
                    self.timelines[company_name] = []

                # 避免重复（同标题+同来源）
                existing = {(e["title"], e["source"]) for e in self.timelines[company_name]}
                if (event["title"], event["source"]) not in existing:
                    self.timelines[company_name].append(event)
                    new_events += 1

        # 按日期排序
        for company in self.timelines:
            self.timelines[company].sort(key=lambda x: x.get("date", ""), reverse=True)

        self._save()
        logger.info(f"[company] 本周新增 {new_events} 条公司事件")

    def update_app_metrics(self, app_items: List[ScrapedItem], week_id: str):
        """将App Store指标作为特殊事件记入公司时间线"""
        for item in app_items:
            app_name = item.extra.get("app_name", "")
            if app_name not in TRACKED_COMPANIES:
                continue

            event = {
                "week_id": week_id,
                "date": week_id,
                "title": f"[数据] {app_name} 评分 {item.extra.get('rating', 'N/A')}, "
                         f"评论 {item.extra.get('review_count', 0):,}",
                "source": "App Store",
                "platform": "appstore",
                "url": item.extra.get("track_url", ""),
                "summary": item.summary,
                "score": 0,
                "metrics": {
                    "rating": item.extra.get("rating"),
                    "review_count": item.extra.get("review_count"),
                    "chart_rank": item.extra.get("chart_rank"),
                },
            }

            if app_name not in self.timelines:
                self.timelines[app_name] = []

            # 每周只记一条指标
            self.timelines[app_name] = [
                e for e in self.timelines[app_name]
                if not (e.get("week_id") == week_id and e.get("platform") == "appstore")
            ]
            self.timelines[app_name].append(event)

        self._save()

    def generate_pages(self):
        """为每家追踪公司生成Hugo页面"""
        os.makedirs(self.content_dir, exist_ok=True)

        # 生成 _index.md
        index_content = """---
title: "公司档案"
description: "短剧漫剧行业重点公司动态追踪"
---

## 追踪公司列表

按类别分组展示，点击公司名查看完整时间线。

"""
        by_category = {}
        for name, info in TRACKED_COMPANIES.items():
            cat = info.get("category", "其他")
            if cat not in by_category:
                by_category[cat] = []
            event_count = len(self.timelines.get(name, []))
            by_category[cat].append((name, info, event_count))

        for cat, companies in by_category.items():
            index_content += f"### {cat}\n\n"
            index_content += "| 公司 | 简介 | 累计事件 |\n"
            index_content += "|------|------|----------|\n"
            for name, info, count in companies:
                slug = name.lower().replace(" ", "-")
                index_content += f"| [{name}](/companies/{slug}/) | {info['description']} | {count} |\n"
            index_content += "\n"

        with open(os.path.join(self.content_dir, "_index.md"), 'w', encoding='utf-8') as f:
            f.write(index_content)

        # 生成各公司页面
        for company_name, info in TRACKED_COMPANIES.items():
            events = self.timelines.get(company_name, [])
            slug = company_name.lower().replace(" ", "-")

            content = f"""---
title: "{company_name}"
description: "{info['description']}"
tags: ["公司档案", "{info.get('category', '')}"]
---

**类别**：{info.get('category', '')}
**简介**：{info['description']}
"""
            if info.get("stock"):
                content += f"**股票代码**：{info['stock']}\n"
            if info.get("parent"):
                content += f"**母公司**：{info['parent']}\n"

            content += f"\n---\n\n## 事件时间线（共 {len(events)} 条）\n\n"

            if events:
                current_week = ""
                for event in events:
                    week = event.get("week_id", "")
                    if week != current_week:
                        content += f"\n### {week}\n\n"
                        current_week = week

                    if event.get("metrics"):
                        m = event["metrics"]
                        content += f"- 📊 **{event['title']}**"
                        if m.get("chart_rank"):
                            content += f" | 免费榜 #{m['chart_rank']}"
                        content += "\n"
                    else:
                        content += f"- **{event['title']}**（{event['source']}）\n"
                        if event.get("summary"):
                            content += f"  > {event['summary'][:100]}\n"
                        if event.get("url"):
                            content += f"  [阅读原文]({event['url']})\n"
                    content += "\n"
            else:
                content += "*暂无相关事件，后续周报采集将自动累积。*\n"

            filepath = os.path.join(self.content_dir, f"{slug}.md")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

        logger.info(f"[company] 已生成 {len(TRACKED_COMPANIES)} 个公司档案页面")
