"""
Apple Podcasts 采集器

通过 iTunes Search API 采集播客单集信息。
API端点：https://itunes.apple.com/search
参数：term, media=podcast, entity=podcastEpisode, country=CN
"""

import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class ApplePodcastsScraper(BaseScraper):
    BASE_URL = "https://itunes.apple.com/search"

    @property
    def source_name(self) -> str:
        return "apple_podcasts"

    def scrape(self, keywords: List[str]) -> List[ScrapedItem]:
        self.results = []
        limits = self.config.get("rate_limits", {}).get("apple_podcasts", {})
        request_interval = limits.get("request_interval", 2)
        max_results = limits.get("max_results_per_keyword", 20)

        for i, keyword in enumerate(keywords):
            if i > 0:
                self.rate_limit(request_interval)

            try:
                items = self._search(keyword, max_results)
                self.results.extend(items)
            except Exception as e:
                logger.error(f"[apple_podcasts] 关键词 '{keyword}' 出错: {e}")

            self.log_progress(keyword, len([r for r in self.results if r.keyword == keyword]))

        logger.info(f"[apple_podcasts] 采集完成，共 {len(self.results)} 条结果")
        return self.results

    def _search(self, term: str, limit: int) -> List[ScrapedItem]:
        """搜索 iTunes/Apple Podcasts API"""
        params = {
            "term": term,
            "media": "podcast",
            "entity": "podcastEpisode",
            "country": "CN",
            "limit": str(limit),
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        items = []
        for result in data.get("results", []):
            try:
                title = result.get("trackName", "")
                collection = result.get("collectionName", "")
                artist = result.get("artistName", "")
                track_url = result.get("trackViewUrl", "")
                description = result.get("description", "") or result.get("shortDescription", "")
                release_date = result.get("releaseDate", "")

                # 截取摘要前200字
                summary = description[:200] if description else ""

                # 额外信息
                extra = {}
                if result.get("trackTimeMillis"):
                    extra["duration_min"] = round(result["trackTimeMillis"] / 60000, 1)
                if collection:
                    extra["podcast_name"] = collection

                items.append(ScrapedItem(
                    source="apple_podcasts",
                    title=title,
                    url=track_url,
                    summary=summary,
                    author=artist or collection,
                    published_at=release_date,
                    keyword=term,
                    extra=extra,
                ))
            except Exception as e:
                logger.debug(f"[apple_podcasts] 解析条目出错: {e}")
                continue

        return items
