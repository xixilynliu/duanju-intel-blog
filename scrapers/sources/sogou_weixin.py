"""
搜狗微信公众号文章采集器

通过搜狗微信搜索（weixin.sogou.com）采集微信公众号文章。
HTML结构：ul.news-list > li > div.txt-box > h3 > a (标题)
                                              p.txt-info (摘要)
                                              span.all-time-y2 (来源账号)
                                              timeConvert('UNIX_TS') (时间戳)
"""

import re
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class SogouWeixinScraper(BaseScraper):
    BASE_URL = "https://weixin.sogou.com/weixin"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    @property
    def source_name(self) -> str:
        return "sogou_weixin"

    def scrape(self, keywords: List[str]) -> List[ScrapedItem]:
        self.results = []
        limits = self.config.get("rate_limits", {}).get("sogou_weixin", {})
        keyword_interval = limits.get("keyword_interval", 15)
        page_interval = limits.get("page_interval", 8)
        captcha_backoff = limits.get("captcha_backoff", 60)
        max_pages = limits.get("max_pages_per_keyword", 3)

        for i, keyword in enumerate(keywords):
            if i > 0:
                self.rate_limit(keyword_interval)

            for page in range(1, max_pages + 1):
                try:
                    html = self._fetch_page(keyword, page)
                    if not html:
                        break

                    # 检测验证码
                    if "用户您好，您的访问过于频繁" in html or "antispider" in html:
                        logger.warning(f"[sogou_weixin] 触发验证码，退避 {captcha_backoff}s")
                        self.rate_limit(captcha_backoff)
                        break

                    items = self._parse_results(html, keyword)
                    self.results.extend(items)

                    if not items:
                        break

                    if page < max_pages:
                        self.rate_limit(page_interval)

                except Exception as e:
                    logger.error(f"[sogou_weixin] 关键词 '{keyword}' 第{page}页出错: {e}")
                    break

            self.log_progress(keyword, len([r for r in self.results if r.keyword == keyword]))

        logger.info(f"[sogou_weixin] 采集完成，共 {len(self.results)} 条结果")
        return self.results

    def _fetch_page(self, keyword: str, page: int) -> str:
        """请求搜狗微信搜索页面"""
        params = {
            "type": "2",
            "query": keyword,
            "page": str(page),
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=self.HEADERS)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                # 搜狗微信页面使用UTF-8编码
                for encoding in ['utf-8', 'gbk', 'gb2312']:
                    try:
                        return raw.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return raw.decode('utf-8', errors='replace')
        except Exception as e:
            logger.error(f"[sogou_weixin] 请求失败: {url} - {e}")
            return ""

    def _parse_results(self, html: str, keyword: str) -> List[ScrapedItem]:
        """解析搜狗微信搜索结果页HTML"""
        items = []
        soup = BeautifulSoup(html, "lxml")
        news_list = soup.select("ul.news-list > li")

        for li in news_list:
            try:
                # 标题和链接
                title_a = li.select_one("div.txt-box h3 a")
                if not title_a:
                    continue
                title = title_a.get_text(strip=True)
                url = title_a.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://weixin.sogou.com" + url

                # 摘要
                summary_p = li.select_one("p.txt-info")
                summary = summary_p.get_text(strip=True) if summary_p else ""

                # 来源账号
                author_span = li.select_one("div.s-p span.all-time-y2")
                author = author_span.get_text(strip=True) if author_span else ""

                # 时间戳
                published_at = ""
                ts_match = re.search(r"timeConvert\('(\d+)'\)", str(li))
                if ts_match:
                    ts = int(ts_match.group(1))
                    published_at = datetime.fromtimestamp(ts).isoformat()

                items.append(ScrapedItem(
                    source="sogou_weixin",
                    title=title,
                    url=url,
                    summary=summary,
                    author=author,
                    published_at=published_at,
                    keyword=keyword,
                ))
            except Exception as e:
                logger.debug(f"[sogou_weixin] 解析条目出错: {e}")
                continue

        return items
