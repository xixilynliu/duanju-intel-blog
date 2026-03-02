"""
相关性评分器

基于多维度加权评分：
- 标题/摘要中的关键词命中
- 已知KOL账号加分
- 播放量/互动量加分（B站）
"""

import logging
import re
from typing import List

from sources.base import ScrapedItem

logger = logging.getLogger(__name__)

# 关键词权重：(关键词, 权重)
PRIORITY_KEYWORDS = [
    ("AI漫剧", 15), ("AIGC短剧", 15), ("AI动漫", 12),
    ("ReelShort", 12), ("ShortTV", 12), ("FlexTV", 10),
    ("短剧出海", 10), ("漫剧", 10), ("短剧", 8),
    ("投放", 8), ("ROI", 10), ("IAA", 10), ("IAP", 10),
    ("DataEye", 10), ("热力榜", 8),
    ("中文在线", 8), ("点众科技", 8), ("九州文化", 8),
    ("容量文化", 8), ("花生短剧", 6), ("红果短剧", 6),
    ("竖屏", 5), ("微短剧", 5), ("互动短剧", 8),
    ("融资", 8), ("上市", 6), ("营收", 8),
    ("政策", 6), ("监管", 6), ("备案", 5),
]


class Scorer:
    def __init__(self, kol_accounts: List[str]):
        self.kol_accounts = set(kol_accounts)

    def score(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """为每个条目计算相关性得分，存入 extra['score']"""
        for item in items:
            s = 0
            text = f"{item.title} {item.summary}".lower()

            # 关键词命中
            for kw, weight in PRIORITY_KEYWORDS:
                if kw.lower() in text:
                    s += weight

            # KOL账号加分
            if item.author in self.kol_accounts:
                s += 20

            # B站播放量加分
            play = item.extra.get("play", 0)
            if play > 100000:
                s += 15
            elif play > 10000:
                s += 8
            elif play > 1000:
                s += 3

            # 播客时长加分（长播客通常质量更高）
            duration = item.extra.get("duration_min", 0)
            if duration > 30:
                s += 5

            item.extra["score"] = s

        # 按分数降序排列
        items.sort(key=lambda x: x.extra.get("score", 0), reverse=True)
        logger.info(f"[scorer] 评分完成，最高分 {items[0].extra.get('score', 0) if items else 0}")
        return items
