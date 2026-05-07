#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仙侠SLG舆情日报 - TrendRadar 后处理脚本
独立版：直接读取 output/ 目录，按日期匹配关键词并生成报告
"""

import os
import re
import sys
import json
import textwrap
from pathlib import Path
from datetime import datetime

# ── 配置 ────────────────────────────────────────────────────────────

MONITOR_KEYWORDS = [
    # 题材
    "仙侠", "修仙", "SLG", "策略游戏", "古装剧", "仙侠剧", "玄幻剧", "武侠剧",
    # 游戏
    "一念逍遥", "崩坏", "原神", "鸣潮", "绝区零", "阴阳师", "火影", "王者荣耀", "剑网",
    # 玄幻动画
    "沧元图", "完美世界", "斗罗大陆", "斗破苍穹",
    # 演员
    "刘诗诗", "刘宇宁", "成毅", "杨紫", "赵丽颖", "肖战", "王一博",
    "任嘉伦", "杨超越", "迪丽热巴", "龚俊", "虞书欣", "王鹤棣",
    # 剧集名
    "一念关山", "长安十二时辰", "长安幻想", "陈情令", "斗破苍穹",
    "雪中悍刀行", "云之羽", "仙剑奇侠传", "苍兰诀", "星落凝成糖",
    "长相思", "长相思2", "沉香如屑", "长月烬明", "安上",
    "来战", "白日提灯", "遮天",
    # 其他
    "氪金", "抽卡", "游戏礼包", "游戏福利",
]

# 正文必须包含以下词汇之一才保留（防止误命中）
CONTENT_CONFIRM_KEYWORDS = [
    "仙侠", "修仙", "玄幻", "古装", "武侠", "抽卡", "氪金", "礼包",
    "游戏", "手游", "SLG", "崩坏", "原神", "鸣潮",
    "沧元图", "斗罗", "斗破", "完美世界",
    "一念关山", "一念逍遥",
]

# ── 工具函数 ──────────────────────────────────────────────────────

def load_news_from_txt(txt_path):
    """从 TrendRadar 的 txt 文件解析出新闻条目列表"""
    if not txt_path.exists():
        return []

    items = []
    with open(txt_path, encoding="utf-8") as f:
        content = f.read()

    # 解析格式：序号\t标题\t链接\t正文摘要（用空行分隔条目）
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue
        first = lines[0].strip()
        # 匹配 "1. 标题" 或 "1\t标题" 格式
        m = re.match(r'^\d+[.)、]\s*([^\t\n]+)', first)
        if not m:
            # 兜底：直接把第一行当作标题
            title = first
        else:
            title = m.group(1).strip()

        url = ""
        body = ""
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("🔗 ") or line.startswith("链接："):
                url = re.sub(r'🔗\s*|\s*链接：', '', line).strip()
            elif line and not line.startswith("📅 "):
                body += line + " "

        items.append({"title": title, "url": url, "body": body.strip()})
    return items


def load_news_from_json(json_dir):
    """从 TrendRadar 的 json 文件解析出新闻条目列表"""
    if not json_dir.exists():
        return []

    items = []
    for json_file in sorted(json_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for entry in data:
                    items.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("url", ""),
                        "body": entry.get("body", entry.get("content", "")),
                    })
        except Exception:
            pass
    return items


def keyword_match(text, keywords):
    """判断文本是否命中任意关键词"""
    if not text:
        return False
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in keywords if len(k) >= 2)


def filter_news(items):
    """两层过滤：标题关键词 + 正文相关性"""
    matched = []
    for item in items:
        title = item.get("title", "")
        body = item.get("body", "")
        combined = title + " " + body

        if not keyword_match(title, MONITOR_KEYWORDS):
            continue
        if body and not keyword_match(body, CONTENT_CONFIRM_KEYWORDS):
            continue
        matched.append(item)
    return matched


def generate_html_report(matched_items, today_str):
    """生成带样式的 HTML 报告"""
    if not matched_items:
        html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>仙侠SLG日报 {today_str}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      max-width:800px;margin:40px auto;padding:0 20px;background:#f8fafc}}
h1{{color:#1e3a5f;border-bottom:3px solid #4a90d9;padding-bottom:10px}}
.info{{color:#666;font-size:14px;margin-bottom:30px}}
.summary{{background:#fff3cd;border-left:4px solid #ffc107;
          padding:15px 20px;border-radius:6px;margin-bottom:30px}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;
          color:#94a3b8;font-size:12px}}
</style></head><body>
<h1>🌟 仙侠SLG热点日报</h1>
<div class="info">📅 {today_str} &nbsp; 📊 11平台实时监控</div>
<div class="summary">
  <strong>今日命中：0 条</strong><br>
  今日热搜中无仙侠/SLG相关热点<br>
  TrendRadar 仅报告真实存在的内容，没有就是没有。
</div>
<div class="footer">
  <p>本报告由 TrendRadar 自动生成 · 数据来源：微博/抖音/知乎/百度/今日头条/哔哩哔哩/华尔街见闻/澎湃/凤凰/贴吧/财联社</p>
</div>
</body></html>"""
    else:
        rows = ""
        for i, item in enumerate(matched_items, 1):
            title = item["title"]
            url = item["url"]
            body = item.get("body", "")
            snippet = textwrap.fill(body[:120], width=80) if body else ""
            rows += f"""<div class="item">
  <div class="num">{i}</div>
  <div class="content">
    <div class="news-title"><a href="{url}" target="_blank">{title}</a></div>
    {"<div class='snippet'>" + snippet + "</div>" if snippet else ""}
  </div>
</div>"""

        html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>仙侠SLG日报 {today_str}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      max-width:800px;margin:40px auto;padding:0 20px;background:#f8fafc}}
h1{{color:#1e3a5f;border-bottom:3px solid #4a90d9;padding-bottom:10px}}
.info{{color:#666;font-size:14px;margin-bottom:30px}}
.item{{display:flex;gap:15px;padding:15px 0;
       border-bottom:1px solid #e2e8f0;align-items:flex-start}}
.num{{background:#4a90d9;color:#fff;border-radius:50%;width:28px;height:28px;
      text-align:center;line-height:28px;font-size:13px;flex-shrink:0;font-weight:700}}
.news-title{{font-size:16px;font-weight:600;color:#1e293b}}
.news-title a{{color:#2563eb;text-decoration:none}}
.news-title a:hover{{text-decoration:underline}}
.snippet{{margin-top:6px;font-size:14px;color:#64748b;line-height:1.5}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;
          color:#94a3b8;font-size:12px}}
</style></head><body>
<h1>🌟 仙侠SLG热点日报</h1>
<div class="info">📅 {today_str} &nbsp; 📊 11平台实时监控</div>
{rows}
<div class="footer">
  <p>本报告由 TrendRadar 自动生成 · 数据来源：微博/抖音/知乎/百度/今日头条/哔哩哔哩/华尔街见闻/澎湃/凤凰/贴吧/财联社</p>
</div>
</body></html>"""
    return html


def get_latest_output_dir(base="output"):
    """找到最新的 output/日期/txt/ 目录"""
    base_path = Path(base)
    if not base_path.exists():
        return None, None

    # 按日期排序找到最新的目录
    date_dirs = []
    for d in base_path.iterdir():
        if d.is_dir() and re.match(r'\d{4}年\d{1,2}月\d{1,2}日', d.name):
            date_dirs.append(d)

    if not date_dirs:
        return None, None

    date_dirs.sort(key=lambda d: d.name, reverse=True)
    latest_date_dir = date_dirs[0]

    # 在日期目录下找 txt/ 或 json/ 子目录
    txt_dir = latest_date_dir / "txt"
    json_dir = latest_date_dir / "json"
    if txt_dir.exists():
        return txt_dir, latest_date_dir.name
    if json_dir.exists():
        return json_dir, latest_date_dir.name
    return None, latest_date_dir.name


def main():
    try:
        # ── Step 1: 找到最新数据 ────────────────────────────────────
        tz_str = os.environ.get("TZ", "")
        if tz_str:
            os.environ["TZ"] = tz_str
        elif "TZ" not in os.environ:
            os.environ["TZ"] = "Asia/Shanghai"
        import time as time_module
        time_module.tzset()

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        print(f"[后处理] 开始分析... 当前时间: {now}")
        print(f"[后处理] 今日日期字符串: {today_str}")

        # 查找最新输出目录
        data_dir, date_label = get_latest_output_dir("output")
        if date_label:
            print(f"[后处理] 找到最新数据目录: output/{date_label}")
        else:
            print("[后处理] 警告: 未找到 output/ 目录，将生成空报告")

        # ── Step 2: 加载数据 ──────────────────────────────────────
        news_items = []

        if data_dir and data_dir.exists():
            # 优先找 txt 文件
            txt_files = list(data_dir.glob("*.txt"))
            if txt_files:
                txt_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                latest_txt = txt_files[0]
                print(f"[后处理] 读取: {latest_txt}")
                news_items = load_news_from_txt(latest_txt)
                print(f"[后处理] 从 txt 解析出 {len(news_items)} 条")

            # 兜底：找 json 文件
            if not news_items:
                json_dir = data_dir.parent / "json"
                news_items = load_news_from_json(json_dir)
                print(f"[后处理] 从 json 解析出 {len(news_items)} 条")

        print(f"[后处理] 共加载 {len(news_items)} 条原始新闻")

        # ── Step 3: 两层过滤 ─────────────────────────────────────
        matched = filter_news(news_items)
        print(f"[后处理] 关键词初筛命中: {sum(1 for i in news_items if keyword_match(i.get('title',''), MONITOR_KEYWORDS))} 条")
        print(f"[后处理] 正文相关性过滤后: {len(matched)} 条")

        if matched:
            print("[后处理] 命中内容:")
            for i in matched:
                print(f"  - {i['title'][:60]}")

        # ── Step 4: 生成报告 ──────────────────────────────────────
        html_content = generate_html_report(matched, today_str)

        # 保存路径：output/2026年05月07日/xianxia/
        xianxia_dir = Path("output") / date_label / "xianxia" if date_label else Path(f"output/{today_str}/xianxia")
        xianxia_dir.mkdir(parents=True, exist_ok=True)

        report_path = xianxia_dir / f"仙侠SLG日报_{today_str.replace('-','')}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"[后处理] ✅ 报告已保存: {report_path}")
        print(f"[后处理] 今日命中: {len(matched)} 条")

    except Exception as e:
        print(f"[后处理] ❌ 发生异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
