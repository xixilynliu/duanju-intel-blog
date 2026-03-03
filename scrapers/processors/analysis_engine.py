"""
核心判断分析引擎

基于采集数据自动生成结构化行业分析判断：
1. 行业格局判断（基于APP指标）
2. 热点话题提取（基于高频关键词聚类）
3. 内容趋势分析（基于采集数据特征）
4. 数据变化信号（基于周环比，有历史数据时）
"""

import logging
import re
from collections import Counter
from typing import List, Dict

from sources.base import ScrapedItem

logger = logging.getLogger(__name__)

# 话题聚类关键词组
TOPIC_CLUSTERS = {
    "AI漫剧": {
        "keywords": ["AI漫剧", "AIGC短剧", "AIGC漫剧", "AI动漫", "AI漫画", "AI短剧"],
        "icon": "🤖",
    },
    "短剧出海": {
        "keywords": ["出海", "海外", "ReelShort", "ShortTV", "FlexTV", "DramaBox",
                      "GoodShort", "北美", "东南亚", "全球", "海外市场"],
        "icon": "🌏",
    },
    "投放与变现": {
        "keywords": ["投放", "ROI", "IAA", "IAP", "买量", "变现", "广告",
                      "付费", "充值", "ARPU", "LTV", "投流"],
        "icon": "💰",
    },
    "行业监管": {
        "keywords": ["政策", "监管", "备案", "审查", "合规", "版权", "牌照"],
        "icon": "📋",
    },
    "融资与资本": {
        "keywords": ["融资", "上市", "IPO", "营收", "利润", "估值", "投资",
                      "市值", "财报", "股价"],
        "icon": "📈",
    },
    "精品化": {
        "keywords": ["精品", "品质", "创新", "升级", "高质量", "工业化"],
        "icon": "⭐",
    },
    "平台竞争": {
        "keywords": ["红果", "番茄", "抖音", "快手", "微信", "小红书",
                      "平台", "竞争", "流量"],
        "icon": "🏟️",
    },
}


class AnalysisEngine:
    """基于采集数据生成结构化核心判断"""

    def generate_core_analysis(
        self,
        content_items: List[ScrapedItem],
        app_metrics: Dict,
        comparison: Dict = None,
        signals: List[Dict] = None,
    ) -> Dict:
        """
        生成核心分析，返回结构化数据供模板渲染。

        返回:
        {
            "summary": "一句话总结",
            "market_landscape": {...},   # 市场格局
            "hot_topics": [...],         # 热点话题
            "content_signals": [...],    # 内容趋势信号
            "data_signals": [...],       # 量化数据信号
            "key_insight": "...",        # 关键洞察
        }
        """
        result = {
            "summary": "",
            "market_landscape": {},
            "hot_topics": [],
            "content_signals": [],
            "data_signals": signals or [],
            "key_insight": "",
        }

        # 1. 市场格局分析（基于APP指标）
        result["market_landscape"] = self._analyze_market(app_metrics, comparison)

        # 2. 热点话题聚类
        result["hot_topics"] = self._cluster_topics(content_items)

        # 3. 内容趋势分析
        result["content_signals"] = self._analyze_content_trends(content_items)

        # 4. 生成一句话总结
        result["summary"] = self._generate_summary(result, content_items)

        # 5. 关键洞察
        result["key_insight"] = self._generate_insight(result, content_items)

        return result

    def _analyze_market(self, app_metrics: Dict, comparison: Dict = None) -> Dict:
        """分析市场格局"""
        market = {
            "overseas": [],
            "domestic": [],
            "overview": "",
        }

        apps = app_metrics if isinstance(app_metrics, dict) else {}
        if comparison and comparison.get("has_data"):
            apps_list = comparison.get("apps", [])
        else:
            # 直接从metrics构建
            apps_list = []
            for name, data in apps.items():
                apps_list.append({
                    "name": name,
                    "country": data.get("country", ""),
                    "rating": data.get("rating", 0),
                    "review_count": data.get("review_count", 0),
                    "chart_rank": data.get("chart_rank"),
                    "review_change": None,
                    "review_change_pct": None,
                    "rank_change": None,
                })

        for app in apps_list:
            entry = {
                "name": app["name"],
                "rating": app.get("rating", 0),
                "review_count": app.get("review_count", 0),
                "chart_rank": app.get("chart_rank"),
                "review_change_pct": app.get("review_change_pct"),
                "rank_change": app.get("rank_change"),
            }
            if app.get("country") == "us":
                market["overseas"].append(entry)
            else:
                market["domestic"].append(entry)

        # 生成格局描述
        overseas_ranked = [a for a in market["overseas"] if a["chart_rank"]]
        domestic_ranked = [a for a in market["domestic"] if a["chart_rank"]]

        parts = []

        if overseas_ranked:
            overseas_ranked.sort(key=lambda x: x["chart_rank"])
            leader = overseas_ranked[0]
            review_leader = max(market["overseas"], key=lambda x: x["review_count"])
            parts.append(
                f"出海赛道：{leader['name']} 和 {overseas_ranked[1]['name'] if len(overseas_ranked) > 1 else '其他竞品'}"
                f"分别位居美区免费榜 #{leader['chart_rank']}"
                f"{'和 #' + str(overseas_ranked[1]['chart_rank']) if len(overseas_ranked) > 1 else ''}"
                f"，{review_leader['name']} 以 {review_leader['review_count']:,} 条评论领跑用户规模"
            )

        if domestic_ranked:
            domestic_ranked.sort(key=lambda x: x["chart_rank"])
            leader = domestic_ranked[0]
            parts.append(
                f"国内赛道：{leader['name']} 稳居免费榜 #{leader['chart_rank']}"
                f"，累计评论 {leader['review_count']:,} 条，是出海头部APP的数倍体量"
            )

        market["overview"] = "；".join(parts) if parts else ""
        return market

    def _cluster_topics(self, items: List[ScrapedItem]) -> List[Dict]:
        """对内容进行话题聚类，返回热度排序的话题列表"""
        topic_scores = {}

        for topic_name, config in TOPIC_CLUSTERS.items():
            count = 0
            matched_items = []
            for item in items:
                text = f"{item.title} {item.summary}"
                if any(kw in text for kw in config["keywords"]):
                    count += 1
                    matched_items.append(item)

            if count > 0:
                # 取该话题下评分最高的文章作为代表
                matched_items.sort(key=lambda x: x.extra.get("score", 0), reverse=True)
                representative = matched_items[0] if matched_items else None
                topic_scores[topic_name] = {
                    "name": topic_name,
                    "icon": config["icon"],
                    "count": count,
                    "pct": round(count / len(items) * 100, 1) if items else 0,
                    "top_title": representative.title if representative else "",
                    "top_source": representative.author if representative else "",
                }

        # 按文章数排序
        sorted_topics = sorted(topic_scores.values(), key=lambda x: x["count"], reverse=True)
        return sorted_topics[:6]  # 最多返回6个话题

    def _analyze_content_trends(self, items: List[ScrapedItem]) -> List[Dict]:
        """分析内容趋势，生成定性信号"""
        signals = []

        if not items:
            return signals

        # 来源分布
        source_counts = Counter(item.source for item in items)
        total = len(items)

        # KOL活跃度
        author_counts = Counter(item.author for item in items)
        active_authors = [a for a, c in author_counts.most_common(5)]

        # 公司提及频率
        company_mentions = Counter()
        for item in items:
            tags = item.extra.get("entity_tags", [])
            for tag in tags:
                company_mentions[tag] += 1

        top_companies = company_mentions.most_common(5)

        # 信号1: 内容体量
        if total >= 500:
            signals.append({
                "icon": "📊",
                "category": "内容体量",
                "text": f"本周共采集 {total} 篇行业内容，信息密度较高，短剧赛道持续受到媒体和行业关注",
                "level": "positive",
            })
        elif total >= 200:
            signals.append({
                "icon": "📊",
                "category": "内容体量",
                "text": f"本周共采集 {total} 篇行业内容，行业保持稳定关注度",
                "level": "neutral",
            })

        # 信号2: 最活跃的信息源
        if active_authors:
            signals.append({
                "icon": "📰",
                "category": "核心信息源",
                "text": f"本周最活跃的信息源：{'、'.join(active_authors[:3])}，建议重点关注其内容",
                "level": "neutral",
            })

        # 信号3: 高频被提及公司
        if top_companies:
            company_parts = [f"{name}（{count}次）" for name, count in top_companies[:5]]
            signals.append({
                "icon": "🏢",
                "category": "公司热度",
                "text": f"被提及最多的公司/平台：{'、'.join(company_parts)}",
                "level": "neutral",
            })

        # 信号4: AI漫剧话题占比
        ai_keywords = ["AI漫剧", "AIGC短剧", "AI动漫", "AI漫画", "AIGC漫剧"]
        ai_count = sum(
            1 for item in items
            if any(kw in f"{item.title} {item.summary}" for kw in ai_keywords)
        )
        if ai_count > 0:
            ai_pct = round(ai_count / total * 100, 1)
            if ai_pct > 15:
                signals.append({
                    "icon": "🤖",
                    "category": "AI漫剧热度",
                    "text": f"AI漫剧相关内容占比达 {ai_pct}%（{ai_count} 篇），已成为行业重要话题",
                    "level": "positive",
                })
            elif ai_pct > 5:
                signals.append({
                    "icon": "🤖",
                    "category": "AI漫剧热度",
                    "text": f"AI漫剧相关内容 {ai_count} 篇（占比 {ai_pct}%），话题热度稳定",
                    "level": "neutral",
                })

        # 信号5: 出海话题占比
        overseas_keywords = ["出海", "海外", "ReelShort", "ShortTV", "FlexTV",
                             "DramaBox", "GoodShort", "北美", "东南亚"]
        overseas_count = sum(
            1 for item in items
            if any(kw in f"{item.title} {item.summary}" for kw in overseas_keywords)
        )
        if overseas_count > 0:
            overseas_pct = round(overseas_count / total * 100, 1)
            if overseas_pct > 15:
                signals.append({
                    "icon": "🌏",
                    "category": "出海热度",
                    "text": f"出海相关内容占比达 {overseas_pct}%（{overseas_count} 篇），短剧出海持续获得高度关注",
                    "level": "positive",
                })
            elif overseas_pct > 5:
                signals.append({
                    "icon": "🌏",
                    "category": "出海热度",
                    "text": f"出海相关内容 {overseas_count} 篇（占比 {overseas_pct}%），关注度稳定",
                    "level": "neutral",
                })

        return signals

    def _generate_summary(self, result: Dict, items: List[ScrapedItem]) -> str:
        """生成一句话总结"""
        parts = []

        # 话题维度
        hot = result.get("hot_topics", [])
        if len(hot) >= 2:
            parts.append(
                f"本周短剧行业讨论热点集中在 **{hot[0]['name']}**（{hot[0]['count']}篇）"
                f"和 **{hot[1]['name']}**（{hot[1]['count']}篇）"
            )

        # 市场维度
        landscape = result.get("market_landscape", {})
        overseas = landscape.get("overseas", [])
        ranked = [a for a in overseas if a.get("chart_rank")]
        if ranked:
            ranked.sort(key=lambda x: x["chart_rank"])
            parts.append(
                f"出海APP竞争格局清晰，{ranked[0]['name']} 和 "
                f"{ranked[1]['name'] if len(ranked) > 1 else '其他竞品'}"
                f" 维持榜单前列"
            )

        # 数据变化维度
        data_signals = result.get("data_signals", [])
        positive_signals = [s for s in data_signals if s.get("level") == "positive"]
        negative_signals = [s for s in data_signals if s.get("level") == "negative"]

        if positive_signals:
            parts.append(f"本周有 {len(positive_signals)} 个积极信号值得关注")
        if negative_signals:
            parts.append(f"{len(negative_signals)} 个下行信号需要警惕")

        if not parts:
            total = len(items) if items else 0
            parts.append(f"本周共采集 {total} 篇行业内容，短剧赛道各维度保持稳定发展态势")

        return "。".join(parts) + "。"

    def _generate_insight(self, result: Dict, items: List[ScrapedItem]) -> str:
        """生成关键洞察（一段投资者视角的分析文字）"""
        insights = []

        # 基于APP数据的洞察
        market = result.get("market_landscape", {})
        overseas = market.get("overseas", [])
        domestic = market.get("domestic", [])

        if overseas:
            # 评论数体量对比
            review_leader = max(overseas, key=lambda x: x["review_count"])
            total_overseas_reviews = sum(a["review_count"] for a in overseas)
            insights.append(
                f"出海短剧APP累计用户评论总量达 {total_overseas_reviews:,} 条"
                f"（{review_leader['name']} 以 {review_leader['review_count']:,} 条领先），"
                f"市场已从验证期进入规模化竞争阶段"
            )

        if domestic:
            top_domestic = max(domestic, key=lambda x: x["review_count"])
            insights.append(
                f"国内市场方面，{top_domestic['name']} 评论量达 {top_domestic['review_count']:,} 条，"
                f"体量远超出海APP，但国内市场以免费+广告模式为主，"
                f"变现效率与出海IAP模式存在显著差异"
            )

        # 基于话题的洞察
        hot = result.get("hot_topics", [])
        ai_topic = next((t for t in hot if t["name"] == "AI漫剧"), None)
        if ai_topic and ai_topic["pct"] > 5:
            insights.append(
                f"AI漫剧以 {ai_topic['pct']}% 的内容占比成为行业新热点，"
                f"技术降本效应正在重塑内容供给侧，值得持续跟踪其产能释放和商业化进展"
            )

        monetize_topic = next((t for t in hot if t["name"] == "投放与变现"), None)
        if monetize_topic:
            insights.append(
                f"投放与变现话题保持活跃（{monetize_topic['count']}篇），"
                f"说明行业已进入精细化运营阶段，ROI和LTV成为竞争核心指标"
            )

        if not insights:
            insights.append(
                "短剧行业整体保持高景气度，建议关注头部平台的用户增长数据和出海APP的排名变化"
            )

        return "。".join(insights) + "。"
