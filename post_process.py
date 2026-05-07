#!/usr/bin/env python3
"""
仙侠SLG舆情日报 - 正文分析 + 报告生成（完全独立版 v3）
不依赖 main.py，直接读取 output/ 下的原始 txt 文件。
"""

import os, re, sys, json, time, urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests
import pytz

TZ = pytz.timezone("Asia/Shanghai")
TODAY = datetime.now(TZ).strftime("%Y年%m月%d日")

# 仙侠/SLG 强相关关键词
RELEVANT_KEYWORDS = [
    # 题材
    "仙侠", "修仙", "SLG", "策略游戏", "三国志", "率土之滨", "万国觉醒",
    "无尽的拉格朗日", "一念逍遥", "梦幻西游", "剑网3", "凡人修仙传",
    "国风", "古风游戏", "修仙手游", "古装剧", "仙侠剧", "玄幻剧",
    "武侠剧", "古偶", "神话剧",
    # 游戏/运营
    "游戏", "手游", "端游", "周年庆", "开服", "版本更新",
    # 演员
    "刘诗诗", "刘宇宁", "成毅", "杨紫", "赵丽颖", "肖战", "王一博",
    "任嘉伦", "杨超越", "迪丽热巴", "龚俊", "虞书欣", "王鹤棣",
    # 具体游戏
    "崩坏", "原神", "鸣潮", "绝区零", "阴阳师", "明日方舟",
    "剑与远征", "放置江湖", "问道", "倩女幽魂", "天涯明月刀",
    "火影", "王者荣耀", "英雄联盟", "原神", "星铁", "星穹铁道",
    # 仙侠/玄幻剧
    "三生三世", "苍兰诀", "长月烬明", "沉香如屑", "与凤行",
    "长相思", "长安十二时辰", "琅琊榜", "陈情令", "山河令",
    "雪中悍刀行", "庆余年", "少年歌行", "长安幻想",
    "来战", "白日提灯", "遮天",
    "沧元图", "完美世界", "斗罗大陆", "斗破苍穹",
]

# 排除词
EXCLUDE_PATTERNS = [
    "广告", "带货", "外挂", "脚本", "诈骗",
    "Cosplay", "同人图", "二手", "出售", "求购",
    "理财", "股票", "基金", "房价", "房产",
]

# 正文泛娱乐/影视强关联词（需同时有题材词才算相关）
FILM_KEYWORDS = ["仙侠剧", "古装剧", "玄幻剧", "武侠剧", "开播", "首播",
                 "定档", "官宣", "杀青", "预告片", "追剧", "剧粉"]


def parse_txt_file(txt_path: Path) -> List[Dict]:
    """解析 TrendRadar txt 文件"""
    items = []
    current_platform = ""
    current_name = ""

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 平台头部行: "weibo | 微博"
            if " | " in line and not re.match(r"^\d+\.", line):
                parts = line.split(" | ", 1)
                if len(parts) == 2:
                    current_platform = parts[0].strip()
                    current_name = parts[1].strip()
                    continue

            # 数据行: "1. title [URL:...] [MOBILE:...]"
            m = re.match(r"^\d+\.\s+(.+)", line)
            if m:
                raw = m.group(1)
                url_m = re.search(r"\[URL:([^\]]+)\]", raw)
                url = url_m.group(1) if url_m else ""
                rank_m = re.match(r"^(\d+)", line)
                rank = rank_m.group(1) if rank_m else "99"
                title = re.sub(r"\[URL:[^\]]+\]", "", raw).strip()
                title = re.sub(r"\[MOBILE:[^\]]+\]", "", title).strip()

                items.append({
                    "platform": current_name or current_platform,
                    "title": title,
                    "url": url,
                    "rank": rank,
                })
    return items


def fetch_content(url: str, timeout: int = 8) -> str:
    """抓取正文，失败或已知不可抓取时返回空"""
    if not url or url == "#":
        return ""
    if "s.weibo.com" in url or "weibo.com/weibo" in url:
        return ""
    if "douyin.com" in url and "/search/" in url:
        return ""
    if "tieba.baidu.com/hottopic" in url:
        return ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.baidu.com/",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = resp.text
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception:
        return ""


def analyze(title: str, content: str) -> Tuple[bool, str]:
    """判断是否相关。返回 (保留, 原因)"""
    # 排除词（标题）
    for pat in EXCLUDE_PATTERNS:
        if pat in title:
            return False, f"标题含排除词：{pat}"

    # 标题直接命中关键词
    title_hit = next((k for k in RELEVANT_KEYWORDS if k in title), None)
    if title_hit:
        return True, f"标题命中：{title_hit}"

    # 无正文时过滤
    if not content:
        return False, "无正文且标题无仙侠/SLG关键词"

    cl = content.lower()

    # 排除词（正文）
    for pat in EXCLUDE_PATTERNS:
        if pat in cl:
            return False, f"正文含排除词：{pat}"

    # 正文关键词命中
    content_hit = next((k for k in RELEVANT_KEYWORDS if k in cl), None)
    if content_hit:
        # 正文有泛娱乐词时才算相关
        if any(k in cl for k in FILM_KEYWORDS):
            return True, f"正文含{content_hit}+影视词"
        return True, f"正文含：{content_hit}"

    return False, "正文无仙侠/SLG相关内容"


def build_report(items: List[Dict], date_str: str, output_dir: Path) -> Path:
    """生成 HTML 报告"""
    base = output_dir / TODAY / "xianxia"
    base.mkdir(parents=True, exist_ok=True)
    filepath = base / f"仙侠SLG日报_{date_str.replace('-', '')}.html"

    by_platform: Dict[str, List] = {}
    for item in items:
        by_platform.setdefault(item["platform"], []).append(item)

    order = ["微博", "抖音", "知乎", "百度热搜", "今日头条", "B站", "贴吧"]
    platforms = sorted(by_platform.keys(),
                       key=lambda x: next((order.index(o) for o in order if o in x), 99))

    sections = ""
    for p in platforms:
        sections += f'<div class="src"><h3>{p}</h3>\n'
        for item in by_platform[p]:
            sections += f"""<div class="ni">
  <span class="rk">#{item["rank"]}</span>
  <div class="bd">
    <a href="{item["url"] or "#"}" target="_blank">{item["title"]}</a>
    <div class="rs">{item.get("reason", "")}</div>
  </div>
</div>\n"""
        sections += "</div>\n"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>仙侠SLG热点日报 {date_str}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#fafafa}}
.hdr{{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:24px;border-radius:12px;margin-bottom:24px}}
.hdr h1{{margin:0 0 8px;font-size:20px}}
.hdr p{{margin:0;opacity:.85;font-size:13px}}
.sum{{background:#fff;padding:16px;border-radius:8px;margin-bottom:16px;border:1px solid #eee}}
.src{{background:#fff;border-radius:8px;padding:16px;margin-bottom:12px;border:1px solid #eee}}
.src h3{{margin:0 0 12px;font-size:14px;color:#4f46e5;border-bottom:1px solid #eee;padding-bottom:8px}}
.ni{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f5f5f5}}
.ni:last-child{{border-bottom:none}}
.rk{{font-weight:700;color:#ea580c;min-width:28px;font-size:14px}}
.bd{{flex:1}}
a{{font-size:14px;color:#1a1a1a;text-decoration:none;line-height:1.5;display:block}}
a:hover{{color:#4f46e5;text-decoration:underline}}
.rs{{font-size:11px;color:#888;margin-top:4px}}
.empty{{text-align:center;padding:40px;color:#888}}
</style></head><body>
<div class="hdr"><h1>仙侠SLG热点日报</h1><p>{date_str} · TrendRadar + 正文分析</p></div>
<div class="sum"><strong>今日命中：{len(items)} 条</strong> · 已过滤无正文/不相关条目</div>
{f'<div class="content">{sections}</div>' if items else '<div class="empty">今日热搜中无仙侠SLG相关热点</div>'}
</body></html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filepath


def send_feishu(items: List[Dict], date_str: str):
    """通过飞书 Webhook 发送通知"""
    webhook = os.environ.get("FEISHU_WEBHOOK", "")
    if not webhook:
        print("FEISHU_WEBHOOK 未设置，跳过推送")
        return

    if not items:
        msg = (f"**仙侠SLG热点日报 · {date_str}**\n\n"
               "今日热搜中无仙侠SLG相关热点\n\n"
               "来源：TrendRadar 11平台实时监控")
    else:
        lines = [f"{i+1}. {it['title']} ({it['platform']}#{it['rank']})"
                 for i, it in enumerate(items[:5])]
        msg = f"**仙侠SLG热点日报 · {date_str}**\n\n今日命中 {len(items)} 条：\n" + "\n".join(lines)

    payload = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15)
    print("飞书通知已发送")


def main():
    # 支持通过参数传入 output 目录，默认使用脚本所在目录
    output_dir = Path(__file__).parent if '__file__' in dir() else Path(".")
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else output_dir

    print("=" * 50)
    print("仙侠SLG舆情日报 - TrendRadar + 正文分析（独立版 v3）")
    print(f"数据目录: {report_path}")
    print("=" * 50)

    txt_dir = report_path / "output" / TODAY / "txt"
    if not txt_dir.exists():
        print(f"未找到目录: {txt_dir}")
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
        fp = build_report([], date_str, report_path)
        send_feishu([], date_str)
        print(f"报告已生成：{fp}")
        return

    # 读取最新 txt 文件
    txt_files = sorted(txt_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txt_files:
        print("未找到 txt 文件")
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
        fp = build_report([], date_str, report_path)
        send_feishu([], date_str)
        return

    latest_txt = txt_files[0]
    print(f"\n读取: {latest_txt}")
    raw_items = parse_txt_file(latest_txt)
    print(f"共 {len(raw_items)} 条原始数据")

    if not raw_items:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")
        fp = build_report([], date_str, report_path)
        send_feishu([], date_str)
        return

    # 逐条分析
    final_items = []
    for i, item in enumerate(raw_items):
        title = item["title"]
        url = item["url"]
        print(f"\n[{i+1}/{len(raw_items)}] {item['platform']} #{item['rank']} {title[:35]}")
        content = fetch_content(url)
        keep, reason = analyze(title, content)
        item["reason"] = reason
        print(f"  {'✓' if keep else '✗'} {reason}")
        if keep:
            final_items.append(item)
        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"分析完成：{len(final_items)} 条保留，{len(raw_items) - len(final_items)} 条过滤")

    date_str = datetime.now(TZ).strftime("%Y-%m-%d")
    fp = build_report(final_items, date_str, report_path)
    print(f"报告已生成：{fp}")
    send_feishu(final_items, date_str)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
