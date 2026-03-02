"""
去重器

基于标题+作者的MD5指纹去重，持久化已见指纹到JSON文件。
"""

import json
import logging
import os
from typing import List

from sources.base import ScrapedItem

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self, fingerprint_path: str):
        self.fingerprint_path = fingerprint_path
        self.seen: set = set()
        self._load()

    def _load(self):
        """从JSON文件加载已有指纹"""
        if os.path.exists(self.fingerprint_path):
            with open(self.fingerprint_path, 'r') as f:
                self.seen = set(json.load(f))
            logger.info(f"[dedup] 加载 {len(self.seen)} 个已有指纹")

    def _save(self):
        """持久化指纹到JSON文件"""
        os.makedirs(os.path.dirname(self.fingerprint_path), exist_ok=True)
        with open(self.fingerprint_path, 'w') as f:
            json.dump(sorted(self.seen), f)

    def deduplicate(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """去重，返回新条目列表"""
        new_items = []
        dup_count = 0

        for item in items:
            fp = item.content_fingerprint()
            if fp not in self.seen:
                self.seen.add(fp)
                new_items.append(item)
            else:
                dup_count += 1

        self._save()
        logger.info(f"[dedup] 输入 {len(items)} 条，去重 {dup_count} 条，剩余 {len(new_items)} 条")
        return new_items
