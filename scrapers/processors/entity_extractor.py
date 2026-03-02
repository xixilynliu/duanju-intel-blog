"""
实体提取器

基于规则匹配从标题和摘要中提取公司名、人物名、平台名。
"""

import re
import logging
from typing import List, Dict, Set

from sources.base import ScrapedItem

logger = logging.getLogger(__name__)

# 已知公司名
KNOWN_COMPANIES = [
    "中文在线", "点众科技", "九州文化", "容量文化", "花生短剧",
    "红果短剧", "ReelShort", "ShortTV", "FlexTV", "DramaBox",
    "抖音", "快手", "腾讯", "爱奇艺", "优酷", "芒果TV",
    "字节跳动", "百度", "阿里", "bilibili", "B站",
    "Crazy Maple Studio", "枫叶互动",
]

# 已知人物名
KNOWN_PERSONS = [
    "杨晓轩", "张牧之", "刘飞", "潘乱", "何立",
]

# 已知平台名
KNOWN_PLATFORMS = [
    "ReelShort", "ShortTV", "FlexTV", "DramaBox", "GoodShort",
    "红果短剧", "花生短剧", "九州短剧", "点众短剧",
    "抖音", "快手", "微信", "小红书",
]


class EntityExtractor:
    def extract(self, items: List[ScrapedItem]) -> Dict[str, Set[str]]:
        """从所有条目中提取实体"""
        entities = {
            "companies": set(),
            "persons": set(),
            "platforms": set(),
        }

        for item in items:
            text = f"{item.title} {item.summary}"

            for company in KNOWN_COMPANIES:
                if company in text:
                    entities["companies"].add(company)

            for person in KNOWN_PERSONS:
                if person in text:
                    entities["persons"].add(person)

            for platform in KNOWN_PLATFORMS:
                if platform in text:
                    entities["platforms"].add(platform)

        logger.info(
            f"[entity] 提取到 {len(entities['companies'])} 家公司, "
            f"{len(entities['persons'])} 位人物, "
            f"{len(entities['platforms'])} 个平台"
        )
        return entities

    def tag_items(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """为每个条目标记涉及的实体"""
        for item in items:
            text = f"{item.title} {item.summary}"
            tags = []

            for company in KNOWN_COMPANIES:
                if company in text:
                    tags.append(company)

            for person in KNOWN_PERSONS:
                if person in text:
                    tags.append(person)

            item.extra["entity_tags"] = tags

        return items
