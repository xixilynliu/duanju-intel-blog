"""
App Store 应用指标采集器

通过 iTunes Lookup API 采集短剧APP的评分、评论数等指标。
同时检查 Apple RSS Top Charts 中的排名情况。
"""

import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# 追踪的核心APP列表
DEFAULT_APPS = {
    # 出海APP（美区）
    "ReelShort": {"id": 1636235979, "country": "us"},
    "DramaBox": {"id": 6445905219, "country": "us"},
    "ShortMax": {"id": 6464002625, "country": "us"},
    "GoodShort": {"id": 6448176203, "country": "us"},
    # 国内APP（中国区）
    "红果短剧": {"id": 6451407032, "country": "cn"},
    "河马剧场": {"id": 6451242037, "country": "cn"},
}

TOP_CHARTS_URL = "https://rss.applemarketingtools.com/api/v2/{country}/apps/top-free/{limit}/apps.json"


class AppStoreScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "appstore"

    def scrape(self, keywords: List[str] = None) -> List[ScrapedItem]:
        """采集APP指标，keywords参数未使用"""
        self.results = []
        apps = self.config.get("tracked_apps", DEFAULT_APPS)

        for app_name, info in apps.items():
            try:
                metrics = self._lookup_app(info["id"], info["country"])
                if metrics:
                    metrics["app_name"] = app_name
                    metrics["country"] = info["country"]
                    self.results.append(ScrapedItem(
                        source="appstore",
                        title=f"{app_name} App Store 数据快照",
                        url=metrics.get("track_url", ""),
                        author=app_name,
                        summary=f"评分 {metrics.get('rating', 'N/A')}, "
                                f"评论数 {metrics.get('review_count', 'N/A')}",
                        extra=metrics,
                    ))
                self.rate_limit(1)
            except Exception as e:
                logger.error(f"[appstore] {app_name} 查询失败: {e}")

        # 查排行榜
        for country in ["us", "cn"]:
            try:
                chart = self._get_top_chart(country, 100)
                self._match_chart_positions(chart, apps, country)
            except Exception as e:
                logger.warning(f"[appstore] {country} 排行榜获取失败: {e}")

        logger.info(f"[appstore] 采集完成，共 {len(self.results)} 条APP数据")
        return self.results

    def _lookup_app(self, app_id: int, country: str) -> Dict:
        """通过 iTunes Lookup API 获取APP详情"""
        url = f"https://itunes.apple.com/lookup?id={app_id}&country={country}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = data.get("results", [])
        if not results:
            return {}

        app = results[0]
        return {
            "app_id": app_id,
            "track_name": app.get("trackName", ""),
            "track_url": app.get("trackViewUrl", ""),
            "rating": round(app.get("averageUserRating", 0), 2),
            "review_count": app.get("userRatingCount", 0),
            "version": app.get("version", ""),
            "release_date": app.get("currentVersionReleaseDate", ""),
            "genre": app.get("primaryGenreName", ""),
            "developer": app.get("artistName", ""),
            "price": app.get("price", 0),
            "content_rating": app.get("contentAdvisoryRating", ""),
        }

    def _get_top_chart(self, country: str, limit: int = 100) -> List[Dict]:
        """获取 App Store 免费榜 TOP N"""
        url = TOP_CHARTS_URL.format(country=country, limit=limit)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        entries = data.get("feed", {}).get("results", [])
        return [
            {"id": e.get("id", ""), "name": e.get("name", ""), "url": e.get("url", "")}
            for e in entries
        ]

    def _match_chart_positions(self, chart: List[Dict], apps: dict, country: str):
        """在排行榜中查找目标APP的排名"""
        chart_ids = {str(e["id"]): i + 1 for i, e in enumerate(chart)}

        for app_name, info in apps.items():
            if info["country"] != country:
                continue
            app_id_str = str(info["id"])
            if app_id_str in chart_ids:
                rank = chart_ids[app_id_str]
                # 找到对应的 ScrapedItem 并更新排名
                for item in self.results:
                    if item.extra.get("app_id") == info["id"]:
                        item.extra["chart_rank"] = rank
                        item.summary += f", 免费榜 #{rank}"
                        logger.info(f"[appstore] {app_name} 在 {country} 免费榜排名 #{rank}")
                        break


def get_app_metrics(config: dict) -> List[Dict]:
    """便捷函数：直接返回结构化的APP指标字典列表"""
    scraper = AppStoreScraper(config)
    items = scraper.scrape()
    return [item.extra for item in items]
