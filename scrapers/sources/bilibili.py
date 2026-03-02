"""
B站视频采集器

通过B站搜索API采集视频信息。
API端点：https://api.bilibili.com/x/web-interface/search/type
参数：search_type=video, keyword=..., order=pubdate
注意：B站有严格的频率限制，超过后返回HTTP 412。
"""

import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class BilibiliScraper(BaseScraper):
    SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json",
    }

    @property
    def source_name(self) -> str:
        return "bilibili"

    def scrape(self, keywords: List[str]) -> List[ScrapedItem]:
        self.results = []
        limits = self.config.get("rate_limits", {}).get("bilibili", {})
        request_interval = limits.get("request_interval", 3)
        max_pages = limits.get("max_pages_per_keyword", 1)

        for i, keyword in enumerate(keywords):
            if i > 0:
                self.rate_limit(request_interval)

            try:
                items = self._search(keyword, max_pages)
                self.results.extend(items)
            except Exception as e:
                logger.error(f"[bilibili] 关键词 '{keyword}' 出错: {e}")

            self.log_progress(keyword, len([r for r in self.results if r.keyword == keyword]))

        logger.info(f"[bilibili] 采集完成，共 {len(self.results)} 条结果")
        return self.results

    def _search(self, keyword: str, max_pages: int) -> List[ScrapedItem]:
        """搜索B站视频"""
        all_items = []

        for page in range(1, max_pages + 1):
            params = {
                "search_type": "video",
                "keyword": keyword,
                "order": "pubdate",
                "page": str(page),
                "page_size": "20",
            }
            url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers=self.HEADERS)

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    status = resp.getcode()
                    if status == 412:
                        logger.warning("[bilibili] HTTP 412 频率限制，停止采集")
                        return all_items
                    data = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                if e.code == 412:
                    logger.warning("[bilibili] HTTP 412 频率限制，停止采集")
                    return all_items
                raise

            if data.get("code") != 0:
                logger.warning(f"[bilibili] API返回错误: {data.get('message', 'unknown')}")
                break

            results = data.get("data", {}).get("result", [])
            if not results:
                break

            for v in results:
                try:
                    # B站搜索结果中标题包含<em>高亮标签，需清理
                    title = v.get("title", "")
                    title = title.replace("<em class=\"keyword\">", "").replace("</em>", "")

                    bvid = v.get("bvid", "")
                    video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""

                    author = v.get("author", "")
                    description = v.get("description", "")[:200]

                    # 时间戳
                    pubdate = v.get("pubdate", 0)
                    published_at = ""
                    if pubdate:
                        published_at = datetime.fromtimestamp(pubdate).isoformat()

                    extra = {
                        "play": v.get("play", 0),
                        "danmaku": v.get("video_review", 0),
                        "favorites": v.get("favorites", 0),
                        "duration": v.get("duration", ""),
                        "mid": v.get("mid", 0),
                    }

                    all_items.append(ScrapedItem(
                        source="bilibili",
                        title=title,
                        url=video_url,
                        summary=description,
                        author=author,
                        published_at=published_at,
                        keyword=keyword,
                        extra=extra,
                    ))
                except Exception as e:
                    logger.debug(f"[bilibili] 解析条目出错: {e}")
                    continue

            if page < max_pages:
                self.rate_limit(3)

        return all_items
