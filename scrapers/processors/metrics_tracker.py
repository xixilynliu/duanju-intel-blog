"""
指标追踪器

存储每周量化指标快照，计算周环比变化。
数据持久化为JSON，每周追加一条记录。
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsTracker:
    def __init__(self, data_path: str):
        """
        data_path: 指标历史数据文件路径，如 data/processed/metrics_history.json
        """
        self.data_path = data_path
        self.history: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
            logger.info(f"[metrics] 加载 {len(self.history)} 条历史记录")

    def _save(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def record_snapshot(self, week_id: str, app_metrics: List[Dict],
                        article_counts: Dict[str, int]):
        """记录本周指标快照"""
        snapshot = {
            "week_id": week_id,
            "recorded_at": datetime.now().isoformat(),
            "apps": {},
            "article_counts": article_counts,
        }

        for m in app_metrics:
            name = m.get("app_name", "unknown")
            snapshot["apps"][name] = {
                "rating": m.get("rating", 0),
                "review_count": m.get("review_count", 0),
                "chart_rank": m.get("chart_rank", None),
                "version": m.get("version", ""),
                "country": m.get("country", ""),
            }

        # 避免同一周重复记录
        self.history = [h for h in self.history if h["week_id"] != week_id]
        self.history.append(snapshot)
        self.history.sort(key=lambda x: x["week_id"])
        self._save()
        logger.info(f"[metrics] 已记录 {week_id} 快照，共追踪 {len(snapshot['apps'])} 个APP")

    def get_comparison(self, week_id: str) -> Dict:
        """获取本周与上周的对比数据"""
        current = None
        previous = None

        for i, h in enumerate(self.history):
            if h["week_id"] == week_id:
                current = h
                if i > 0:
                    previous = self.history[i - 1]
                break

        if not current:
            return {"has_data": False}

        result = {
            "has_data": True,
            "week_id": week_id,
            "prev_week_id": previous["week_id"] if previous else None,
            "apps": [],
            "articles": {},
        }

        # APP 对比
        for app_name, cur_data in current.get("apps", {}).items():
            row = {
                "name": app_name,
                "country": cur_data.get("country", ""),
                "rating": cur_data.get("rating", 0),
                "review_count": cur_data.get("review_count", 0),
                "chart_rank": cur_data.get("chart_rank"),
                "rating_change": None,
                "review_change": None,
                "review_change_pct": None,
                "rank_change": None,
            }

            if previous and app_name in previous.get("apps", {}):
                prev_data = previous["apps"][app_name]
                prev_rating = prev_data.get("rating", 0)
                prev_reviews = prev_data.get("review_count", 0)
                prev_rank = prev_data.get("chart_rank")

                if prev_rating:
                    row["rating_change"] = round(cur_data.get("rating", 0) - prev_rating, 2)
                if prev_reviews:
                    row["review_change"] = cur_data.get("review_count", 0) - prev_reviews
                    if prev_reviews > 0:
                        row["review_change_pct"] = round(
                            (cur_data.get("review_count", 0) - prev_reviews) / prev_reviews * 100, 1
                        )
                if prev_rank and cur_data.get("chart_rank"):
                    # 排名下降是正数（不好），上升是负数（好），取反让"上升"为正
                    row["rank_change"] = prev_rank - cur_data.get("chart_rank", 0)

            result["apps"].append(row)

        # 文章数对比
        cur_articles = current.get("article_counts", {})
        prev_articles = previous.get("article_counts", {}) if previous else {}

        for source, count in cur_articles.items():
            prev_count = prev_articles.get(source, 0)
            change = count - prev_count if prev_count else None
            result["articles"][source] = {
                "count": count,
                "prev_count": prev_count,
                "change": change,
            }

        return result

    def generate_signals(self, comparison: Dict) -> List[Dict]:
        """基于对比数据生成信号判断"""
        signals = []

        if not comparison.get("has_data"):
            return signals

        for app in comparison.get("apps", []):
            name = app["name"]

            # 排名大幅变化
            rank_change = app.get("rank_change")
            if rank_change is not None:
                if rank_change >= 10:
                    signals.append({
                        "category": "出海" if app["country"] == "us" else "国内",
                        "level": "positive",
                        "text": f"{name} 免费榜排名上升 {rank_change} 位至 #{app['chart_rank']}",
                    })
                elif rank_change <= -10:
                    signals.append({
                        "category": "出海" if app["country"] == "us" else "国内",
                        "level": "negative",
                        "text": f"{name} 免费榜排名下降 {abs(rank_change)} 位至 #{app['chart_rank']}",
                    })

            # 评论数暴增（说明用户增长加速）
            review_pct = app.get("review_change_pct")
            if review_pct is not None and review_pct > 20:
                signals.append({
                    "category": "出海" if app["country"] == "us" else "国内",
                    "level": "positive",
                    "text": f"{name} 新增评论数周环比 +{review_pct}%，用户增长加速",
                })

        # 文章热度信号
        total_cur = sum(a["count"] for a in comparison.get("articles", {}).values())
        total_prev = sum(a["prev_count"] for a in comparison.get("articles", {}).values())
        if total_prev > 0:
            change_pct = (total_cur - total_prev) / total_prev * 100
            if change_pct > 30:
                signals.append({
                    "category": "行业热度",
                    "level": "positive",
                    "text": f"行业文章产出量周环比 +{change_pct:.0f}%，舆论关注度升温",
                })
            elif change_pct < -30:
                signals.append({
                    "category": "行业热度",
                    "level": "negative",
                    "text": f"行业文章产出量周环比 {change_pct:.0f}%，关注度回落",
                })

        return signals
