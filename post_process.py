#!/usr/bin/env python3
"""
仙侠SLG舆情日报 - 正文分析 + 报告生成
在 TrendRadar 采集结果基础上，做正文级别的相关性判断，
只保留真正与仙侠/SLG/泛娱乐借势相关的条目。
"""

import os
import re
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests
import yaml
import pytz

# 加载 TrendRadar 的配置和数据解析逻辑
sys.path.insert(0, str(Path(__file__).parent))
from main import (
    load_config,
    read_all_today_titles,
    load_frequency_words,
    get_output_path,
    format_date_folder,
    format_time_filename,
    ensure_directory_exists,
    clean_title,
)

# ========== 正文分析相关 ==========

# 与仙侠/SLG 强相关的关键词（正文必须包含至少一个）
RELEVANT_KEYWORDS = [
    "仙侠", "修仙", "SLG", "策略", "三国志", "率土之滨", "万国觉醒",
    "无尽的拉格朗日", "一念逍遥", "梦幻西游", "剑网3", "凡人修仙传",
    "国风", "古风游戏", "修仙手游", "古装剧", "仙侠剧", "玄幻剧",
    "武侠剧", "古偶", "神话剧",
    "游戏", "手游", "端游", "版本更新", "周年庆", "开服", "上线",
]

# 正文必须不含排除词（否则过滤）
EXCLUDE_PATTERNS = [
    "广告", "带货", "短视频", "外挂", "脚本", "诈骗",
    "Cosplay", "同人图", "二手", "出售", "求购",
]

# 正文弱相关词（单独存在不够，需要有游戏/仙侠/古装其中之一）
GAME_ENTHUSIAST_KEYWORDS = [
    "氪金", "零氪", "微氪", "肝", "福利", "礼包", "周年庆",
    "开服", "版本", "更新", "bug", "优化", "策划",
]


def fetch_article_content(url: str, timeout: int = 8) -> str:
    """抓取文章正文，失败返回空字符串"""
    if not url or url == "#":
        return ""

    # Weibo 搜索页、话题页无法抓正文，直接返回空
    if "weibo.com/weibo" in url or "s.weibo.com" in url:
        return ""
    if "douyin.com" in url and "/search/" in url:
        return ""
    if "tieba.baidu.com/hottopic" in url:
        return ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.baidu.com/",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = resp.text

        # 提取正文：常见方案
        # 1. 移除 script/style
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.I)
        # 2. 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', text)
        # 3. 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:3000]  # 最多取前 3000 字符

    except Exception as e:
        return ""


def analyze_relevance(title: str, content: str, url: str) -> Tuple[bool, str]:
    """
    判断条目是否真正相关。
    返回 (is_relevant, reason)
    """
    title_lower = title.lower()
    content_lower = content.lower()

    # Weibo/抖音 搜索页 - 无正文，用标题判断
    if "weibo.com" in url and ("weibo.com/weibo" in url or "s.weibo.com" in url):
        if any(k in title for k in RELEVANT_KEYWORDS):
            return True, "热搜话题标题直接命中仙侠/SLG/古装关键词"
        elif any(k in title for k in GAME_ENTHUSIAST_KEYWORDS) and any(k in title for k in ["游戏", "仙侠", "古装", "玄幻", "武侠"]):
            return True, "热搜话题标题含游戏+泛娱乐关键词"
        else:
            return False, "无正文，仅标题无仙侠/SLG关键词"

    # 有正文的情况
    if not content:
        # 无正文但标题有关键词，谨慎通过
        if any(k in title for k in RELEVANT_KEYWORDS):
            return True, f"无正文，标题关键词命中：{next((k for k in RELEVANT_KEYWORDS if k in title), '')}"
        return False, "无正文且标题无相关关键词"

    # 排除检查
    for pat in EXCLUDE_PATTERNS:
        if pat in content_lower or pat in title_lower:
            return False, f"内容含排除词：{pat}"

    # 正文相关性分析
    title_relevant = any(k in title_lower for k in RELEVANT_KEYWORDS)
    content_relevant = any(k in content_lower for k in RELEVANT_KEYWORDS)
    content_game = any(k in content_lower for k in GAME_ENTHUSIAST_KEYWORDS)

    # 强相关：正文直接包含仙侠/SLG/古装/游戏
    if content_relevant and content_game:
        return True, "正文含游戏相关+仙侠/SLG/古装内容"
    if content_relevant:
        return True, "正文直接包含仙侠/SLG/古装/游戏关键词"
    if title_relevant and content_game:
        return True, "标题关键词+正文含游戏相关内容"
    if title_relevant:
        return True, "标题直接含仙侠/SLG/古装关键词"

    # 弱相关但可能有用
    if content_game:
        # 检查正文是否提到具体游戏或仙侠内容
        if any(k in content_lower for k in ["剧", "演员", "播出", "开播", "上线"]):
            return True, "正文含影视相关内容，可能是泛娱乐借势素材"
        return False, "正文仅含游戏泛娱乐词，无仙侠/SLG核心关键词"

    return False, "正文无仙侠/SLG/游戏相关内容"


# ========== 报告生成相关 ==========

def build_news_item(
    title: str,
    source_name: str,
    platform: str,
    rank: int,
    url: str,
    mobile_url: str,
    reason: str,
) -> Dict:
    """构造传给 generate_html_report 的 news item 结构"""
    return {
        "title": title,
        "source_name": source_name,
        "platform": platform,
        "rank": rank,
        "url": url,
        "mobile_url": mobile_url,
        "reason": reason,
        "time_display": "",
    }


def generate_simple_report(news_items: List[Dict], date_str: str) -> str:
    """生成简化的仙侠SLG日报 HTML"""
    ensure_directory_exists("output")
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / "xianxia"
    ensure_directory_exists(str(output_dir))
    filename = f"仙侠SLG日报_{date_str.replace('-', '')}.html"
    filepath = output_dir / filename

    # 按来源分组
    by_source = {}
    for item in news_items:
        src = item.get("source_name", item.get("platform", "未知"))
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(item)

    # 排序：微博优先，再按排名
    platform_order = ["微博", "抖音", "知乎", "百度热搜", "今日头条", "B站热搜", "贴吧", "其他"]
    sorted_sources = sorted(by_source.keys(), key=lambda x: next((platform_order.index(p) for p in platform_order if p in x), 99))

    items_html = ""
    for src in sorted_sources:
        items_html += f'<div class="source-section"><h3>{src}</h3>'
        for item in by_source[src]:
            rank = item.get("rank", "-")
            title = item["title"]
            url = item.get("url", "#")
            reason = item.get("reason", "")
            items_html += f"""
            <div class="news-item">
                <span class="rank">#{rank}</span>
                <div class="item-body">
                    <a class="news-title" href="{url}" target="_blank">{title}</a>
                    <div class="reason">{reason}</div>
                </div>
            </div>"""
        items_html += "</div>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>仙侠SLG热点日报 {date_str}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#fafafa}}
.header{{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;padding:24px;border-radius:12px;margin-bottom:24px}}
.header h1{{margin:0 0 8px;font-size:20px}}
.header p{{margin:0;opacity:0.85;font-size:13px}}
.summary{{background:white;padding:16px;border-radius:8px;margin-bottom:16px;border:1px solid #eee}}
.source-section{{background:white;border-radius:8px;padding:16px;margin-bottom:12px;border:1px solid #eee}}
.source-section h3{{margin:0 0 12px;font-size:14px;color:#4f46e5;border-bottom:1px solid #eee;padding-bottom:8px}}
.news-item{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f5f5f5}}
.news-item:last-child{{border-bottom:none}}
.rank{{font-weight:700;color:#ea580c;min-width:28px;font-size:14px}}
.item-body{{flex:1}}
.news-title{{font-size:14px;color:#1a1a1a;text-decoration:none;line-height:1.5}}
.news-title:hover{{color:#4f46e5;text-decoration:underline}}
.reason{{font-size:11px;color:#888;margin-top:4px}}
.empty{{text-align:center;padding:40px;color:#888;font-size:15px}}
</style></head><body>
<div class="header">
  <h1>仙侠SLG热点日报</h1>
  <p>{date_str} · TrendRadar + 正文分析</p>
</div>
<div class="summary">
  <strong>今日命中：{len(news_items)} 条</strong> · 已过滤无正文/不相关条目
</div>
{f'<div class="content">{items_html}</div>' if news_items else '<div class="empty">今日热搜中无仙侠SLG相关热点</div>'}
</body></html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return str(filepath.absolute())


# ========== 主流程 ==========

def main():
    print("=" * 50)
    print("仙侠SLG舆情日报 - TrendRadar + 正文分析")
    print("=" * 50)

    # 1. 加载配置和当天数据
    load_config()
    current_platform_ids = ["weibo", "douyin", "zhihu", "baidu", "toutiao",
                              "bilibili-hot-search", "wallstreetcn-hot", "thepaper", "ifeng", "tieba", "cls-hot"]

    all_results, id_to_name, title_info = read_all_today_titles(current_platform_ids)
    word_groups, filter_words = load_frequency_words()

    if not all_results:
        print("未找到当天数据，请先运行 TrendRadar main.py")
        return

    # 2. 第一层过滤：关键词匹配
    from main import matches_word_groups
    candidates = []

    for source_id, titles_data in all_results.items():
        source_name = id_to_name.get(source_id, source_id)
        for title, title_data in titles_data.items():
            matches = matches_word_groups(title, word_groups, filter_words)
            if not matches:
                continue

            ranks = title_data.get("ranks", [])
            rank = ranks[0] if ranks else 99
            url = title_data.get("url", "")
            mobile_url = title_data.get("mobileUrl", "")

            candidates.append({
                "title": clean_title(title),
                "source_id": source_id,
                "source_name": source_name,
                "rank": rank,
                "url": url,
                "mobile_url": mobile_url,
            })

    print(f"\n第一层关键词匹配：{len(candidates)} 条候选")

    if not candidates:
        # 无候选也要生成空报告
        date_str = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")
        filepath = generate_simple_report([], date_str)
        print(f"无相关热点，已生成空报告：{filepath}")
        return

    # 3. 第二层过滤：正文分析
    final_items = []
    skip_count = 0

    for i, cand in enumerate(candidates):
        title = cand["title"]
        url = cand["url"]
        source = cand["source_name"]

        print(f"\n[{i+1}/{len(candidates)}] {source} #{cand['rank']} {title[:30]}")
        print(f"  URL: {url[:60] if url else '(无)'}")

        content = fetch_article_content(url)
        is_relevant, reason = analyze_relevance(title, content, url)

        print(f"  结论: {'✓ 保留' if is_relevant else '✗ 过滤'} - {reason}")

        if is_relevant:
            final_items.append({
                **cand,
                "reason": reason,
                "content_preview": content[:200] if content else "",
            })
        else:
            skip_count += 1

        # 请求间隔，避免过于频繁
        time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"正文分析完成：{len(final_items)} 条保留，{skip_count} 条过滤")

    # 4. 生成报告
    date_str = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")
    filepath = generate_simple_report(final_items, date_str)
    print(f"报告已生成：{filepath}")

    return filepath, final_items


if __name__ == "__main__":
    main()
