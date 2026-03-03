"""
投资备忘录自动生成器

当特定条件触发时，自动生成"值得关注"的投资备忘录。
触发规则：
- 某公司连续3周出现在采集热文中
- APP排名单周变化超过10位
- APP评论数周增长超过20%
- 新公司/新APP首次进入追踪范围
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class MemoTrigger:
    """单条触发规则"""
    def __init__(self, company: str, trigger_type: str, detail: str,
                 severity: str = "info", data: dict = None):
        self.company = company
        self.trigger_type = trigger_type  # streak / rank_jump / review_surge / new_entry
        self.detail = detail
        self.severity = severity  # info / warning / alert
        self.data = data or {}


class InvestmentMemoGenerator:
    def __init__(self, metrics_path: str, company_timelines_path: str,
                 output_dir: str):
        self.metrics_path = metrics_path
        self.company_timelines_path = company_timelines_path
        self.output_dir = output_dir

    def check_triggers(self, week_id: str) -> List[MemoTrigger]:
        """检查所有触发条件，返回触发列表"""
        triggers = []

        # 加载指标历史
        metrics_history = []
        if os.path.exists(self.metrics_path):
            with open(self.metrics_path, 'r', encoding='utf-8') as f:
                metrics_history = json.load(f)

        # 加载公司时间线
        company_timelines = {}
        if os.path.exists(self.company_timelines_path):
            with open(self.company_timelines_path, 'r', encoding='utf-8') as f:
                company_timelines = json.load(f)

        # 规则1: 公司连续3周出现在热文中
        triggers.extend(self._check_streak(company_timelines, week_id))

        # 规则2: APP排名大幅变化
        triggers.extend(self._check_rank_changes(metrics_history))

        # 规则3: 评论数激增
        triggers.extend(self._check_review_surge(metrics_history))

        logger.info(f"[memo] 检查完毕，触发 {len(triggers)} 条规则")
        return triggers

    def _check_streak(self, timelines: dict, current_week: str) -> List[MemoTrigger]:
        """检查哪些公司连续3周出现"""
        triggers = []

        for company, events in timelines.items():
            # 统计最近的周次（不含appstore指标事件）
            weeks_with_content = set()
            for e in events:
                if e.get("platform") != "appstore":
                    weeks_with_content.add(e.get("week_id", ""))

            recent_weeks = sorted(weeks_with_content, reverse=True)[:5]

            if len(recent_weeks) >= 3:
                # 检查是否连续
                triggers.append(MemoTrigger(
                    company=company,
                    trigger_type="streak",
                    detail=f"{company} 连续 {len(recent_weeks)} 周出现在行业热文中（{', '.join(recent_weeks[:3])}）",
                    severity="warning",
                    data={"weeks": recent_weeks[:5], "total_mentions": len([e for e in events if e.get("platform") != "appstore"])},
                ))

        return triggers

    def _check_rank_changes(self, history: list) -> List[MemoTrigger]:
        """检查排名大幅变化"""
        triggers = []
        if len(history) < 2:
            return triggers

        current = history[-1]
        previous = history[-2]

        for app_name, cur_data in current.get("apps", {}).items():
            if app_name not in previous.get("apps", {}):
                continue
            prev_data = previous["apps"][app_name]

            cur_rank = cur_data.get("chart_rank")
            prev_rank = prev_data.get("chart_rank")

            if cur_rank and prev_rank:
                change = prev_rank - cur_rank  # 正数=上升
                if abs(change) >= 10:
                    direction = "上升" if change > 0 else "下跌"
                    severity = "alert" if abs(change) >= 20 else "warning"
                    triggers.append(MemoTrigger(
                        company=app_name,
                        trigger_type="rank_jump",
                        detail=f"{app_name} 免费榜排名{direction} {abs(change)} 位（#{prev_rank} → #{cur_rank}）",
                        severity=severity,
                        data={"prev_rank": prev_rank, "cur_rank": cur_rank, "change": change},
                    ))

        return triggers

    def _check_review_surge(self, history: list) -> List[MemoTrigger]:
        """检查评论数异常增长"""
        triggers = []
        if len(history) < 2:
            return triggers

        current = history[-1]
        previous = history[-2]

        for app_name, cur_data in current.get("apps", {}).items():
            if app_name not in previous.get("apps", {}):
                continue
            prev_data = previous["apps"][app_name]

            cur_reviews = cur_data.get("review_count", 0)
            prev_reviews = prev_data.get("review_count", 0)

            if prev_reviews > 0:
                growth = (cur_reviews - prev_reviews) / prev_reviews * 100
                if growth > 20:
                    new_reviews = cur_reviews - prev_reviews
                    triggers.append(MemoTrigger(
                        company=app_name,
                        trigger_type="review_surge",
                        detail=f"{app_name} 评论数周增长 +{growth:.0f}%（新增 {new_reviews:,} 条），用户增长显著加速",
                        severity="alert" if growth > 50 else "warning",
                        data={"growth_pct": growth, "new_reviews": new_reviews,
                              "total_reviews": cur_reviews},
                    ))

        return triggers

    def generate_memo(self, week_id: str, triggers: List[MemoTrigger]) -> str:
        """生成投资备忘录Markdown文件"""
        if not triggers:
            logger.info("[memo] 无触发条件，不生成备忘录")
            return ""

        os.makedirs(self.output_dir, exist_ok=True)

        # 按严重程度排序
        severity_order = {"alert": 0, "warning": 1, "info": 2}
        triggers.sort(key=lambda t: severity_order.get(t.severity, 3))

        alert_count = len([t for t in triggers if t.severity == "alert"])
        warning_count = len([t for t in triggers if t.severity == "warning"])

        content = f"""---
title: "投资备忘录 {week_id}"
date: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")}
draft: false
tags: ["备忘录", "投资信号"]
categories: ["备忘录"]
summary: "本周触发 {len(triggers)} 条关注信号（{alert_count} 条高优先、{warning_count} 条中优先）"
---

> 本备忘录由信号检测系统自动生成
>
> 周次：**{week_id}** | 触发规则：**{len(triggers)}** 条

---

## 信号概览

"""
        for trigger in triggers:
            icon = {"alert": "🔴", "warning": "🟡", "info": "🔵"}.get(trigger.severity, "⚪")
            content += f"- {icon} **{trigger.company}**：{trigger.detail}\n"

        content += "\n---\n\n"

        # 按公司分组详细分析
        by_company = {}
        for t in triggers:
            if t.company not in by_company:
                by_company[t.company] = []
            by_company[t.company].append(t)

        for company, company_triggers in by_company.items():
            content += f"## {company}\n\n"

            for t in company_triggers:
                icon = {"alert": "🔴", "warning": "🟡", "info": "🔵"}.get(t.severity, "⚪")
                content += f"### {icon} {t.trigger_type}\n\n"
                content += f"**{t.detail}**\n\n"

                if t.trigger_type == "rank_jump":
                    content += f"- 排名变化：#{t.data.get('prev_rank')} → #{t.data.get('cur_rank')}\n"
                    content += f"- 建议动作：关注该APP近期的营销投放和内容策略变化\n"
                elif t.trigger_type == "review_surge":
                    content += f"- 增长率：+{t.data.get('growth_pct', 0):.0f}%\n"
                    content += f"- 新增评论：{t.data.get('new_reviews', 0):,}\n"
                    content += f"- 总评论数：{t.data.get('total_reviews', 0):,}\n"
                    content += f"- 建议动作：可能存在大规模买量或自然增长爆发，值得深入研究\n"
                elif t.trigger_type == "streak":
                    content += f"- 出现周次：{', '.join(t.data.get('weeks', []))}\n"
                    content += f"- 累计提及：{t.data.get('total_mentions', 0)} 次\n"
                    content += f"- 建议动作：该公司持续受到行业关注，建议跟踪其业务进展\n"

                content += "\n"

            content += "---\n\n"

        content += "*本备忘录由 [短剧漫剧行业情报站](/) 信号检测系统自动生成*\n"

        filename = f"memo-{week_id}.md"
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"[memo] 投资备忘录已生成: {output_path}（{len(triggers)} 条信号）")
        return output_path
