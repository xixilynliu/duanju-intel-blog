"""
指标图表生成器

读取 metrics_history.json，生成 SVG 趋势图表，
保存到 Hugo static 目录，供仪表盘页面嵌入。
"""

import json
import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)

# SVG 配置
CHART_WIDTH = 800
CHART_HEIGHT = 300
PADDING = {"top": 40, "right": 30, "bottom": 60, "left": 70}
COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]
BG_COLOR = "#1e1e2e"
GRID_COLOR = "#333355"
TEXT_COLOR = "#cdd6f4"


def _scale(value, min_val, max_val, min_px, max_px):
    if max_val == min_val:
        return (min_px + max_px) / 2
    return min_px + (value - min_val) / (max_val - min_val) * (max_px - min_px)


def _format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def generate_line_chart(data_points: List[Dict], title: str,
                        y_label: str, output_path: str):
    """
    生成折线图SVG。
    data_points: [{"label": "W01", "series": {"ReelShort": 354000, "DramaBox": 700000, ...}}, ...]
    """
    if not data_points:
        return

    plot_left = PADDING["left"]
    plot_right = CHART_WIDTH - PADDING["right"]
    plot_top = PADDING["top"]
    plot_bottom = CHART_HEIGHT - PADDING["bottom"]
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    # 收集所有系列名
    all_series = set()
    for dp in data_points:
        all_series.update(dp.get("series", {}).keys())
    all_series = sorted(all_series)

    # 计算Y轴范围
    all_values = []
    for dp in data_points:
        all_values.extend(dp.get("series", {}).values())
    all_values = [v for v in all_values if v is not None]
    if not all_values:
        return
    y_min = min(all_values) * 0.9
    y_max = max(all_values) * 1.1
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}">')
    svg_parts.append(f'<rect width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{BG_COLOR}" rx="8"/>')

    # 标题
    svg_parts.append(f'<text x="{CHART_WIDTH/2}" y="24" text-anchor="middle" '
                     f'fill="{TEXT_COLOR}" font-size="14" font-weight="bold">{title}</text>')

    # Y轴网格和标签
    num_grid = 5
    for i in range(num_grid + 1):
        y_val = y_min + (y_max - y_min) * i / num_grid
        y_px = plot_bottom - (i / num_grid) * plot_height
        svg_parts.append(f'<line x1="{plot_left}" y1="{y_px}" x2="{plot_right}" y2="{y_px}" '
                         f'stroke="{GRID_COLOR}" stroke-width="1"/>')
        svg_parts.append(f'<text x="{plot_left - 8}" y="{y_px + 4}" text-anchor="end" '
                         f'fill="{TEXT_COLOR}" font-size="11">{_format_number(int(y_val))}</text>')

    # Y轴标签
    svg_parts.append(f'<text x="15" y="{(plot_top + plot_bottom)/2}" text-anchor="middle" '
                     f'fill="{TEXT_COLOR}" font-size="11" transform="rotate(-90, 15, {(plot_top + plot_bottom)/2})">'
                     f'{y_label}</text>')

    # 绘制每个系列
    n_points = len(data_points)
    for si, series_name in enumerate(all_series):
        color = COLORS[si % len(COLORS)]
        points = []

        for di, dp in enumerate(data_points):
            val = dp.get("series", {}).get(series_name)
            if val is None:
                continue
            x_px = plot_left + (di / max(n_points - 1, 1)) * plot_width
            y_px = _scale(val, y_min, y_max, plot_bottom, plot_top)
            points.append((x_px, y_px))

        if len(points) < 2:
            continue

        # 折线
        path_d = f"M {points[0][0]:.1f},{points[0][1]:.1f}"
        for x, y in points[1:]:
            path_d += f" L {x:.1f},{y:.1f}"
        svg_parts.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.5"/>')

        # 数据点
        for x, y in points:
            svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')

        # 最后一个值标注
        last_x, last_y = points[-1]
        last_val = data_points[-1].get("series", {}).get(series_name, 0)
        svg_parts.append(f'<text x="{last_x + 5}" y="{last_y - 8}" fill="{color}" '
                         f'font-size="10">{_format_number(int(last_val))}</text>')

    # X轴标签
    for di, dp in enumerate(data_points):
        x_px = plot_left + (di / max(n_points - 1, 1)) * plot_width
        label = dp.get("label", "")
        # 只显示部分标签避免拥挤
        if n_points <= 8 or di % max(1, n_points // 8) == 0 or di == n_points - 1:
            svg_parts.append(f'<text x="{x_px}" y="{plot_bottom + 18}" text-anchor="middle" '
                             f'fill="{TEXT_COLOR}" font-size="10">{label}</text>')

    # 图例
    legend_y = CHART_HEIGHT - 12
    legend_x = plot_left
    for si, series_name in enumerate(all_series):
        color = COLORS[si % len(COLORS)]
        x_offset = legend_x + si * 110
        svg_parts.append(f'<rect x="{x_offset}" y="{legend_y - 8}" width="12" height="12" '
                         f'rx="2" fill="{color}"/>')
        svg_parts.append(f'<text x="{x_offset + 16}" y="{legend_y + 2}" fill="{TEXT_COLOR}" '
                         f'font-size="10">{series_name}</text>')

    svg_parts.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_parts))

    logger.info(f"[charts] 图表已生成: {output_path}")


def generate_rank_chart(data_points: List[Dict], title: str, output_path: str):
    """
    排名图表（Y轴翻转，#1在上方）。
    data_points: [{"label": "W01", "series": {"ReelShort": 3, "DramaBox": 8}}, ...]
    """
    if not data_points:
        return

    plot_left = PADDING["left"]
    plot_right = CHART_WIDTH - PADDING["right"]
    plot_top = PADDING["top"]
    plot_bottom = CHART_HEIGHT - PADDING["bottom"]
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    all_series = set()
    for dp in data_points:
        all_series.update(dp.get("series", {}).keys())
    all_series = sorted(all_series)

    # 排名范围（翻转：小数字在上方）
    all_values = []
    for dp in data_points:
        all_values.extend(v for v in dp.get("series", {}).values() if v is not None)
    if not all_values:
        return
    rank_min = 1
    rank_max = max(all_values) + 5

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}">')
    svg_parts.append(f'<rect width="{CHART_WIDTH}" height="{CHART_HEIGHT}" fill="{BG_COLOR}" rx="8"/>')
    svg_parts.append(f'<text x="{CHART_WIDTH/2}" y="24" text-anchor="middle" '
                     f'fill="{TEXT_COLOR}" font-size="14" font-weight="bold">{title}</text>')

    # Y轴（排名，#1在上面）
    grid_ranks = [1, 10, 25, 50, 100]
    for rank in grid_ranks:
        if rank > rank_max:
            continue
        y_px = _scale(rank, rank_min, rank_max, plot_top, plot_bottom)
        svg_parts.append(f'<line x1="{plot_left}" y1="{y_px}" x2="{plot_right}" y2="{y_px}" '
                         f'stroke="{GRID_COLOR}" stroke-width="1"/>')
        svg_parts.append(f'<text x="{plot_left - 8}" y="{y_px + 4}" text-anchor="end" '
                         f'fill="{TEXT_COLOR}" font-size="11">#{rank}</text>')

    n_points = len(data_points)
    for si, series_name in enumerate(all_series):
        color = COLORS[si % len(COLORS)]
        points = []

        for di, dp in enumerate(data_points):
            val = dp.get("series", {}).get(series_name)
            if val is None:
                continue
            x_px = plot_left + (di / max(n_points - 1, 1)) * plot_width
            y_px = _scale(val, rank_min, rank_max, plot_top, plot_bottom)
            points.append((x_px, y_px, val))

        if len(points) < 2:
            continue

        path_d = f"M {points[0][0]:.1f},{points[0][1]:.1f}"
        for x, y, _ in points[1:]:
            path_d += f" L {x:.1f},{y:.1f}"
        svg_parts.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.5"/>')

        for x, y, v in points:
            svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')

        last_x, last_y, last_v = points[-1]
        svg_parts.append(f'<text x="{last_x + 5}" y="{last_y - 8}" fill="{color}" '
                         f'font-size="10">#{int(last_v)}</text>')

    # X轴标签
    for di, dp in enumerate(data_points):
        x_px = plot_left + (di / max(n_points - 1, 1)) * plot_width
        label = dp.get("label", "")
        if n_points <= 8 or di % max(1, n_points // 8) == 0 or di == n_points - 1:
            svg_parts.append(f'<text x="{x_px}" y="{plot_bottom + 18}" text-anchor="middle" '
                             f'fill="{TEXT_COLOR}" font-size="10">{label}</text>')

    legend_y = CHART_HEIGHT - 12
    for si, series_name in enumerate(all_series):
        color = COLORS[si % len(COLORS)]
        x_offset = plot_left + si * 110
        svg_parts.append(f'<rect x="{x_offset}" y="{legend_y - 8}" width="12" height="12" '
                         f'rx="2" fill="{color}"/>')
        svg_parts.append(f'<text x="{x_offset + 16}" y="{legend_y + 2}" fill="{TEXT_COLOR}" '
                         f'font-size="10">{series_name}</text>')

    svg_parts.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_parts))

    logger.info(f"[charts] 排名图表已生成: {output_path}")


class DashboardGenerator:
    def __init__(self, metrics_path: str, static_dir: str, content_dir: str):
        """
        metrics_path: metrics_history.json路径
        static_dir: hugo-site/static/charts/
        content_dir: hugo-site/content/
        """
        self.metrics_path = metrics_path
        self.static_dir = static_dir
        self.content_dir = content_dir

    def generate(self):
        """读取历史数据，生成所有图表和仪表盘页面"""
        if not os.path.exists(self.metrics_path):
            logger.warning("[dashboard] 无历史指标数据，跳过图表生成")
            return

        with open(self.metrics_path, 'r', encoding='utf-8') as f:
            history = json.load(f)

        if len(history) < 1:
            logger.warning("[dashboard] 历史数据不足，跳过图表生成")
            return

        charts_dir = os.path.join(self.static_dir, "charts")

        # 1. 评论数趋势图（出海APP）
        review_data = []
        for snapshot in history:
            week = snapshot["week_id"].split("-")[1]  # W09
            series = {}
            for app_name, data in snapshot.get("apps", {}).items():
                if data.get("country") == "us":
                    series[app_name] = data.get("review_count", 0)
            review_data.append({"label": week, "series": series})

        generate_line_chart(
            review_data,
            "出海短剧APP评论数趋势",
            "评论数",
            os.path.join(charts_dir, "overseas_reviews.svg"),
        )

        # 2. 评论数趋势图（国内APP）
        cn_review_data = []
        for snapshot in history:
            week = snapshot["week_id"].split("-")[1]
            series = {}
            for app_name, data in snapshot.get("apps", {}).items():
                if data.get("country") == "cn":
                    series[app_name] = data.get("review_count", 0)
            cn_review_data.append({"label": week, "series": series})

        generate_line_chart(
            cn_review_data,
            "国内短剧APP评论数趋势",
            "评论数",
            os.path.join(charts_dir, "cn_reviews.svg"),
        )

        # 3. 排名趋势图（出海APP）
        rank_data = []
        for snapshot in history:
            week = snapshot["week_id"].split("-")[1]
            series = {}
            for app_name, data in snapshot.get("apps", {}).items():
                if data.get("country") == "us" and data.get("chart_rank"):
                    series[app_name] = data["chart_rank"]
            if series:
                rank_data.append({"label": week, "series": series})

        if rank_data:
            generate_rank_chart(
                rank_data,
                "出海短剧APP免费榜排名走势",
                os.path.join(charts_dir, "overseas_ranks.svg"),
            )

        # 4. 文章产出量趋势
        article_data = []
        for snapshot in history:
            week = snapshot["week_id"].split("-")[1]
            series = snapshot.get("article_counts", {})
            article_data.append({"label": week, "series": series})

        generate_line_chart(
            article_data,
            "各平台行业文章产出量趋势",
            "文章数",
            os.path.join(charts_dir, "article_volume.svg"),
        )

        # 生成仪表盘页面
        self._generate_dashboard_page(history)

        logger.info("[dashboard] 仪表盘生成完成")

    def _generate_dashboard_page(self, history):
        """生成Hugo仪表盘页面"""
        latest = history[-1] if history else {}
        week_id = latest.get("week_id", "N/A")

        content = f"""---
title: "数据仪表盘"
layout: "page"
description: "短剧漫剧行业核心指标追踪"
---

> 数据截至 **{week_id}**，共累积 **{len(history)}** 周数据

---

## 出海APP评论数趋势

评论数增长反映用户规模扩张速度。

![出海短剧APP评论数趋势](/charts/overseas_reviews.svg)

---

## 国内APP评论数趋势

![国内短剧APP评论数趋势](/charts/cn_reviews.svg)

---

## 出海APP免费榜排名走势

排名越低（#1为最高）表示市场表现越好。

![出海短剧APP排名走势](/charts/overseas_ranks.svg)

---

## 行业文章产出量趋势

各平台关于短剧/漫剧的文章发布数量，反映行业关注度。

![文章产出量趋势](/charts/article_volume.svg)

---

## 最新数据快照

"""
        # 添加最新一周的数据表格
        if latest.get("apps"):
            content += "### APP 指标\n\n"
            content += "| APP | 市场 | 评分 | 评论数 | 免费榜 |\n"
            content += "|-----|------|------|--------|--------|\n"
            for app_name, data in sorted(latest["apps"].items()):
                country = "🇺🇸" if data.get("country") == "us" else "🇨🇳"
                rank = f"#{data['chart_rank']}" if data.get("chart_rank") else "未进榜"
                content += (f"| {app_name} | {country} | {data.get('rating', 'N/A')} | "
                            f"{data.get('review_count', 0):,} | {rank} |\n")

        content += "\n---\n\n*图表每周自动更新*\n"

        os.makedirs(self.content_dir, exist_ok=True)
        with open(os.path.join(self.content_dir, "dashboard.md"), 'w', encoding='utf-8') as f:
            f.write(content)
