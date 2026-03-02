"""
短剧漫剧行业情报站 — 采集基础模块

统一数据结构和采集器抽象基类。
"""

import hashlib
import re
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScrapedItem:
    """统一的采集数据容器"""
    source: str           # 数据来源平台：sogou_weixin / apple_podcasts / bilibili
    title: str            # 标题
    url: str              # 原文链接
    summary: str = ""     # 摘要
    author: str = ""      # 作者/账号名
    published_at: str = ""  # 发布时间（ISO格式字符串）
    scraped_at: str = ""  # 采集时间
    keyword: str = ""     # 触发该结果的搜索关键词
    extra: dict = field(default_factory=dict)  # 额外字段（播放量、时长等）

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()

    def content_fingerprint(self) -> str:
        """基于标题+作者的MD5指纹，用于去重"""
        normalized = re.sub(r'\s+', '', f"{self.title}|{self.author}").lower()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


class BaseScraper(ABC):
    """采集器抽象基类"""

    def __init__(self, config: dict):
        self.config = config
        self.results: List[ScrapedItem] = []

    @abstractmethod
    def scrape(self, keywords: List[str]) -> List[ScrapedItem]:
        """执行采集，返回采集结果列表"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称"""
        pass

    def rate_limit(self, seconds: float):
        """速率控制"""
        logger.debug(f"[{self.source_name}] 等待 {seconds}s...")
        time.sleep(seconds)

    def log_progress(self, keyword: str, count: int):
        logger.info(f"[{self.source_name}] 关键词 '{keyword}' 采集到 {count} 条结果")
