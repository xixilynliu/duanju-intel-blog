#!/usr/bin/env python3
"""
短剧漫剧行业情报站 — 采集管线编排器

用法：
  python3 main.py                     # 完整流程：采集 → 处理 → 生成周报
  python3 main.py --scrape-only       # 仅采集
  python3 main.py --generate-only     # 仅生成周报（使用已有数据）
  python3 main.py --week 2026-W09     # 指定周数
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import yaml

from sources.sogou_weixin import SogouWeixinScraper
from sources.apple_podcasts import ApplePodcastsScraper
from sources.bilibili import BilibiliScraper
from sources.appstore import AppStoreScraper, get_app_metrics
from processors.deduplicator import Deduplicator
from processors.scorer import Scorer
from processors.entity_extractor import EntityExtractor
from processors.metrics_tracker import MetricsTracker
from processors.company_profiles import CompanyProfileManager
from generators.weekly_report import WeeklyReportGenerator
from generators.dashboard import DashboardGenerator
from generators.investment_memo import InvestmentMemoGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_week_id(week: str = None) -> str:
    """获取周标识，格式：YYYY-WNN"""
    if week:
        return week
    now = datetime.now()
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def run_scrapers(config: dict) -> list:
    """运行所有采集器"""
    all_keywords = []
    for group in config.get("keywords", {}).values():
        all_keywords.extend(group)

    all_items = []

    # 搜狗微信
    logger.info("=" * 50)
    logger.info("开始采集：搜狗微信")
    sogou = SogouWeixinScraper(config)
    items = sogou.scrape(all_keywords)
    all_items.extend(items)

    # Apple Podcasts
    logger.info("=" * 50)
    logger.info("开始采集：Apple Podcasts")
    podcasts = ApplePodcastsScraper(config)
    podcast_keywords = config.get("keywords", {}).get("core", all_keywords[:5])
    items = podcasts.scrape(podcast_keywords)
    all_items.extend(items)

    # B站
    logger.info("=" * 50)
    logger.info("开始采集：B站")
    bili = BilibiliScraper(config)
    bili_keywords = config.get("keywords", {}).get("core", all_keywords[:3])
    items = bili.scrape(bili_keywords)
    all_items.extend(items)

    # App Store 指标
    logger.info("=" * 50)
    logger.info("开始采集：App Store")
    appstore = AppStoreScraper(config)
    items = appstore.scrape()
    all_items.extend(items)

    logger.info("=" * 50)
    logger.info(f"采集完成，共 {len(all_items)} 条原始结果")
    return all_items


def process_items(config: dict, items: list) -> list:
    """处理管线：去重 → 评分 → 实体标记"""
    fingerprint_path = config.get("paths", {}).get(
        "fingerprint_db", "data/processed/fingerprints.json"
    )

    # 去重（仅对内容类 item）
    content_items = [i for i in items if i.source != "appstore"]
    app_items = [i for i in items if i.source == "appstore"]

    dedup = Deduplicator(fingerprint_path)
    content_items = dedup.deduplicate(content_items)

    # 评分
    kol_accounts = config.get("kol_accounts", [])
    scorer = Scorer(kol_accounts)
    content_items = scorer.score(content_items)

    # 实体标记
    extractor = EntityExtractor()
    content_items = extractor.tag_items(content_items)

    return content_items + app_items


def save_raw_data(items: list, week_id: str, raw_dir: str):
    """保存原始数据到JSON"""
    os.makedirs(raw_dir, exist_ok=True)
    output_path = os.path.join(raw_dir, f"{week_id}.json")
    data = [item.to_dict() for item in items]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"原始数据已保存到 {output_path}")
    return output_path


def save_processed_data(items: list, week_id: str, processed_dir: str):
    """保存处理后数据"""
    os.makedirs(processed_dir, exist_ok=True)
    output_path = os.path.join(processed_dir, f"{week_id}.json")
    data = [item.to_dict() for item in items]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"处理后数据已保存到 {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="短剧漫剧行业情报 采集管线")
    parser.add_argument("--scrape-only", action="store_true", help="仅采集，不生成周报")
    parser.add_argument("--generate-only", action="store_true", help="仅生成周报")
    parser.add_argument("--week", type=str, default=None, help="指定周数，如 2026-W09")
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)
    week_id = get_week_id(args.week)
    logger.info(f"当前周次：{week_id}")

    raw_dir = config.get("paths", {}).get("raw_data", "data/raw")
    processed_dir = config.get("paths", {}).get("processed_data", "data/processed")
    hugo_content = config.get("paths", {}).get("hugo_content", "../hugo-site/content")
    hugo_data = config.get("paths", {}).get("hugo_data", "../hugo-site/data")
    metrics_path = os.path.join(processed_dir, "metrics_history.json")

    if args.generate_only:
        # 从已有处理后数据生成周报
        processed_path = os.path.join(processed_dir, f"{week_id}.json")
        if not os.path.exists(processed_path):
            logger.error(f"找不到处理后数据文件: {processed_path}")
            sys.exit(1)
        with open(processed_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        from sources.base import ScrapedItem
        items = []
        for d in data:
            items.append(ScrapedItem(**d))
    else:
        # 执行采集
        raw_items = run_scrapers(config)
        save_raw_data(raw_items, week_id, raw_dir)

        # 处理
        items = process_items(config, raw_items)
        save_processed_data(items, week_id, processed_dir)

        if args.scrape_only:
            logger.info("仅采集模式，跳过周报生成")
            return

    # 指标追踪
    logger.info("=" * 50)
    logger.info("更新指标追踪")
    tracker = MetricsTracker(metrics_path)

    app_items = [i for i in items if i.source == "appstore"]
    content_items = [i for i in items if i.source != "appstore"]
    app_metrics = [i.extra for i in app_items]

    article_counts = {
        "微信公众号": len([i for i in content_items if i.source == "sogou_weixin"]),
        "播客": len([i for i in content_items if i.source == "apple_podcasts"]),
        "B站": len([i for i in content_items if i.source == "bilibili"]),
    }
    tracker.record_snapshot(week_id, app_metrics, article_counts)

    comparison = tracker.get_comparison(week_id)
    signals = tracker.generate_signals(comparison)

    logger.info(f"生成 {len(signals)} 条信号判断")

    # 生成周报
    logger.info("=" * 50)
    logger.info("开始生成周报")

    # 加载手动笔记
    manual_notes_dir = os.path.join(hugo_data, "manual_notes")
    manual_notes_path = os.path.join(manual_notes_dir, f"{week_id}.yaml")
    manual_notes = {}
    if os.path.exists(manual_notes_path):
        with open(manual_notes_path, 'r', encoding='utf-8') as f:
            manual_notes = yaml.safe_load(f) or {}
        logger.info(f"已加载手动笔记: {manual_notes_path}")

    generator = WeeklyReportGenerator(
        template_dir="generators/templates",
        output_dir=os.path.join(hugo_content, "weekly"),
    )
    output_path = generator.generate(
        items, week_id, manual_notes,
        comparison=comparison,
        signals=signals,
        app_count=len(app_items),
        app_metrics=tracker.history[-1].get("apps", {}) if tracker.history else {},
    )
    logger.info(f"周报已生成: {output_path}")

    # 公司档案更新
    logger.info("=" * 50)
    logger.info("更新公司档案")
    company_data_path = os.path.join(hugo_data, "company_timelines.json")
    company_content_dir = os.path.join(hugo_content, "companies")
    company_mgr = CompanyProfileManager(company_data_path, company_content_dir)
    company_mgr.update_from_items(content_items, week_id)
    company_mgr.update_app_metrics(app_items, week_id)
    company_mgr.generate_pages()

    # 仪表盘图表生成
    logger.info("=" * 50)
    logger.info("生成仪表盘图表")
    hugo_static = os.path.join(hugo_content, "..", "static")
    dashboard = DashboardGenerator(metrics_path, hugo_static, hugo_content)
    dashboard.generate()

    # 投资备忘录
    logger.info("=" * 50)
    logger.info("检查投资备忘录触发条件")
    memo_gen = InvestmentMemoGenerator(
        metrics_path=metrics_path,
        company_timelines_path=company_data_path,
        output_dir=os.path.join(hugo_content, "memos"),
    )
    memo_triggers = memo_gen.check_triggers(week_id)
    if memo_triggers:
        memo_path = memo_gen.generate_memo(week_id, memo_triggers)
        logger.info(f"投资备忘录已生成: {memo_path}")
    else:
        logger.info("本周无触发条件，未生成备忘录")

    logger.info("=" * 50)
    logger.info("完成！请运行 'cd ../hugo-site && hugo server -D' 预览")


if __name__ == "__main__":
    main()
