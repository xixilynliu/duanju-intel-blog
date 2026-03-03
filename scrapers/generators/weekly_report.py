"""
周报生成器

加载处理后的数据，分类整理，通过Jinja2模板渲染Markdown周报文件，
写入Hugo content目录。
"""

import os
import logging
from datetime import datetime
from typing import List, Dict

from jinja2 import Environment, FileSystemLoader

from sources.base import ScrapedItem
from processors.entity_extractor import EntityExtractor
from processors.analysis_engine import AnalysisEngine

logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    def __init__(self, template_dir: str, output_dir: str):
        self.template_dir = template_dir
        self.output_dir = output_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            keep_trailing_newline=True,
        )

    def generate(self, items: List[ScrapedItem], week_id: str,
                 manual_notes: dict = None,
                 comparison: dict = None, signals: list = None,
                 app_count: int = 0,
                 app_metrics: dict = None) -> str:
        """生成周报Markdown文件"""
        # 过滤掉 appstore 类型的 item（它们的数据走 comparison 通道）
        content_items = [i for i in items if i.source != "appstore"]

        # 分类
        weixin_items = [i for i in content_items if i.source == "sogou_weixin"]
        podcast_items = [i for i in content_items if i.source == "apple_podcasts"]
        bili_items = [i for i in content_items if i.source == "bilibili"]

        # 按评分排序
        weixin_items.sort(key=lambda x: x.extra.get("score", 0), reverse=True)
        podcast_items.sort(key=lambda x: x.extra.get("score", 0), reverse=True)
        bili_items.sort(key=lambda x: x.extra.get("play", 0), reverse=True)

        # 综合TOP（所有来源混合，不含appstore）
        top_items = sorted(content_items, key=lambda x: x.extra.get("score", 0), reverse=True)

        # AI漫剧筛选
        ai_keywords = ["AI漫剧", "AIGC短剧", "AI动漫", "AI漫画", "AIGC漫剧"]
        ai_items = [
            i for i in content_items
            if any(kw in f"{i.title} {i.summary}" for kw in ai_keywords)
        ]

        # 出海筛选
        overseas_keywords = ["出海", "ReelShort", "ShortTV", "FlexTV", "DramaBox", "海外", "North America", "Southeast Asia"]
        overseas_items = [
            i for i in content_items
            if any(kw in f"{i.title} {i.summary}" for kw in overseas_keywords)
        ]

        # 实体提取
        extractor = EntityExtractor()
        entities_raw = extractor.extract(content_items)
        entities = {k: sorted(v) for k, v in entities_raw.items()}

        # 手动笔记
        notes_list = []
        if manual_notes:
            notes_list = manual_notes.get("notes", [])

        # 默认值
        if comparison is None:
            comparison = {"has_data": False}
        if signals is None:
            signals = []
        if app_metrics is None:
            app_metrics = {}

        # 核心分析引擎
        engine = AnalysisEngine()
        analysis = engine.generate_core_analysis(
            content_items=content_items,
            app_metrics=app_metrics,
            comparison=comparison,
            signals=signals,
        )

        # 渲染模板
        template = self.env.get_template("weekly_template.md.j2")
        rendered = template.render(
            week_id=week_id,
            generated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            total_count=len(content_items),
            weixin_count=len(weixin_items),
            podcast_count=len(podcast_items),
            bili_count=len(bili_items),
            app_count=app_count,
            top_items=top_items,
            weixin_items=weixin_items,
            podcast_items=podcast_items,
            bili_items=bili_items,
            ai_items=ai_items,
            overseas_items=overseas_items,
            entities=entities,
            manual_notes=notes_list,
            comparison=comparison,
            signals=signals,
            analysis=analysis,
        )

        # 写入文件
        os.makedirs(self.output_dir, exist_ok=True)
        filename = f"{week_id}.md"
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered)

        logger.info(f"[generator] 周报已写入: {output_path}")
        return output_path
