#!/usr/bin/env python3
"""
盯盘小助手 — 定时推送（个性化持仓版）
使用 quote_engine 获取数据，从 stock_watch 读取实际持仓/监控
"""

import json, sys, os, urllib.request
from datetime import datetime
from pathlib import Path

# 引入自研引擎和持仓配置
sys.path.insert(0, os.path.dirname(__file__))
import quote_engine as qe
import importlib.util

# 加载持仓阈值
THRESHOLDS_PATH = os.path.join(os.path.dirname(__file__), "stock_watch.py")
spec = importlib.util.spec_from_file_location("watchcfg", THRESHOLDS_PATH)
watchcfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchcfg)

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dec20a90-d24b-42d0-8f55-c77e2e37c818"
LAOZHANG_ID = "ou_0e554d5177c5cedbf66573e7e5d2f038"
MY_ID = "ou_e3f9c80f19f1c38f8d5e53b3a78879d5"

# ── 获取持有仓位 + 监控票 ──

def get_holdings():
    """从THRESHOLDS提取当前持仓（cost>0 且没清仓）"""
    holdings = []
    for code, cfg in watchcfg.THRESHOLDS.items():
        pos = cfg.get("pos", "")
        if "清仓" in pos:
            continue
        # 从中提取股数
        import re
        m = re.search(r"(\d+)股", pos)
        qty = int(m.group(1)) if m else 0
        if qty > 0:
            holdings.append((code, cfg["name"], cfg.get("cost", 0), qty, pos))
    return holdings

def get_active_watchlist():
    """从THRESHOLDS提取监控票（在观察但未持仓）"""
    watch = []
    for code, cfg in watchcfg.THRESHOLDS.items():
        pos = cfg.get("pos", "")
        if "观察" in pos:
            watch.append((code, cfg["name"]))
    return watch

# ── 数据获取 (使用quote_engine) ──

def get_idx_quote():
    """获取大盘指数"""
    q = qe.get_quote("000001")
    if not q:
        # fallback 腾讯
        import requests
        r = requests.get("http://qt.gtimg.cn/q=sh000001", timeout=5)
        r.encoding = "gbk"
        p = r.text.split("~")
        if len(p) >= 34:
            return {"p": float(p[3]), "c": float(p[32]) if p[32] else 0,
                    "o": float(p[5]) if p[5] else 0, "h": float(p[33]), "l": float(p[34])}
        return {"p": 0, "c": 0, "o": 0, "h": 0, "l": 0}
    return {"p": q["price"], "c": q.get("change_pct", 0), "o": q.get("open", 0),
            "h": q.get("high", 0), "l": q.get("low", 0)}

def holdings_block(holdings):
    """持仓收益块"""
    lines = []
    total = 0
    for code, name, cost, qty, pos in holdings:
        q = qe.get_quote(code)
        if not q:
            continue
        p = q["price"]
        pct = (p - cost) / cost * 100 if cost > 0 else 0
        cny = (p - cost) * qty if cost > 0 else 0
        total += cny
        e = "📈" if pct > 0 else ("📉" if pct < 0 else "➖")
        color = "red" if pct > 0 else ("green" if pct < 0 else "grey")
        lines.append(f"**{name}** {qty}股: {p}  <font color='{color}'>{pct:+.2f}% ({'+' if cny>0 else ''}{cny:.0f}元)</font>")
    return "\n".join(lines), total

def watch_block(watchlist):
    """关注票状态块（只显示靠近买点的）"""
    lines = []
    for code, name in watchlist:
        _, _, price, det = qe.get_live_ma(code)
        if not det:
            continue
        near = det.get("near_ma5_pct", 99)
        # 只显示偏离小的
        if near < 1.5:
            lines.append(f"**{name}**: {price}  偏离5日线{near:.1f}% ✅")
    return "\n".join(lines) if lines else "暂无靠近买点的关注票"

# ── 推送函数 ──

def push(title, template, main_text, col_pairs=None, bottom_text="", buttons=None):
    """发送飞书卡片"""
    # @老张 在消息开头
    mention = f"<at user_id=\"{MY_ID}\">小G</at> 盯盘信号触发，请帮我分析：\n\n"
    main_text = mention + main_text
    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": main_text}},
        {"tag": "hr"},
    ]
    if col_pairs:
        cols = []
        for t, c in col_pairs:
            cols.append({
                "tag": "column", "width": "weighted", "weight": 1, "vertical_align": "top",
                "elements": [{"tag": "markdown", "content": f"**{t}**\n{c}"}]
            })
        elements.append({
            "tag": "column_set", "flex_mode": "none", "background_style": "grey",
            "columns": cols
        })
        elements.append({"tag": "hr"})
    if bottom_text:
        elements.append({"tag": "markdown", "content": bottom_text})
        elements.append({"tag": "hr"})
    if buttons:
        actions = []
        for btn_text, btn_type, btn_val in buttons:
            actions.append({
                "tag": "button", "text": {"tag": "plain_text", "content": btn_text},
                "type": btn_type, "value": {"command": btn_val}
            })
        elements.append({"tag": "action", "actions": actions})
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": f"⏰ {datetime.now().strftime('%m-%d %H:%M')} · 数据仅供参考"}
    ]})

    payload = json.dumps({
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": template},
            "elements": elements
        }
    }).encode("utf-8")
    try:
        urllib.request.urlopen(urllib.request.Request(WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}), timeout=10)
        print("  ✅ 推送成功")
    except Exception as e:
        print(f"  ❌ 推送失败: {e}")

# ═══ 定时任务 ═══

def morning():
    """集合竞价 09:25"""
    idx = get_idx_quote()
    holdings = get_holdings()
    rows, total = holdings_block(holdings)
    templ = "red" if idx["c"] > 0 else "green"
    dir_txt = "高开偏强" if idx["c"] > 0 else ("低开偏弱" if idx["c"] < 0 else "平开")

    push(
        title=f"📈 集合竞价 · {dir_txt}",
        template=templ,
        main_text=f"大盘{dir_txt}，注意集合竞价方向。\n**情绪：** <font color='{'red' if idx['c']>0 else 'green'}'>{'偏乐观' if idx['c']>0 else '偏谨慎'}</font>",
        col_pairs=[
            ("📉 大盘", f"上证 {idx['p']}  {idx['c']:+.2f}%\n昨收 {idx['p']/(1+idx['c']/100):.0f}"),
            ("🎯 关键", f"压力 4100/4150\n支撑 4060/4000"),
        ],
        bottom_text=f"### 👤 我的持仓\n{rows}" if rows else "",
        buttons=[("已操作 ✅", "primary", "act_alerts"), ("忽略 ⏸", "default", "ignore_card")]
    )

def open5():
    """开盘5分钟 09:35"""
    idx = get_idx_quote()
    holdings = get_holdings()
    up = idx["c"] >= 0
    rows, total = holdings_block(holdings)
    judge = "开盘站稳，全天偏强" if up else "开盘回落，弱势"

    push(
        title=f"{'🚀' if up else '⚠️'} 开盘5分钟",
        template="red" if up else "green",
        main_text=f"{judge}\n**策略：** {'<font color=\"red\">回踩不破可加仓</font>' if up else '<font color=\"green\">反弹减仓</font>'}",
        col_pairs=[
            ("📊 上证", f"{idx['p']}  {idx['c']:+.2f}%\n开 {idx['o']}"),
            ("⚡ 定势", f"{'📈 高开' if up else '📉 低开'}"),
        ],
        bottom_text=f"### 👤 持仓\n{rows}" if rows else "",
        buttons=[("已操作 ✅", "primary", "act_alerts"), ("忽略 ⏸", "default", "ignore_card")]
    )

def open30():
    """开盘半小时 10:00"""
    idx = get_idx_quote()
    holdings = get_holdings()
    rows, total = holdings_block(holdings)
    watch_rows = watch_block(get_active_watchlist())

    push(
        title=f"📊 开盘半小时{' 🟢' if total>=0 else ' 🔴'}",
        template="red" if total >= 0 else "green",
        main_text=f"总浮盈 <font color=\"{'red' if total>=0 else 'green'}\">{'+' if total>=0 else ''}{total:.0f}元</font>",
        col_pairs=[
            ("📊 大盘", f"{idx['p']}  {idx['c']:+.2f}%\n高 {idx['h']}  低 {idx['l']}"),
            ("🎯 策略", f"{'持有等涨' if total>=0 else '控制仓位'}"),
        ],
        bottom_text=f"### 👤 持仓\n{rows}\n\n### 📡 关注票靠近5日线\n{watch_rows}" if rows else "",
        buttons=[("已操作 ✅", "primary", "act_alerts"), ("忽略 ⏸", "default", "ignore_card")]
    )


def send_mention_card(title, template, main_text, col_pairs=None, bottom_text="", buttons=None):
    """先发文字@mention，再发卡片"""
    mention_text = f"<at user_id=\"{MY_ID}\">小G</at> 盯盘信号触发，请帮我分析："
    # Send text first for @mention
    try:
        text_payload = {
            "msg_type": "text",
            "content": {"text": mention_text}
        }
        data = json.dumps(text_payload).encode("utf-8")
        urllib.request.urlopen(urllib.request.Request(WEBHOOK_URL, data=data,
            headers={"Content-Type": "application/json"}), timeout=10)
        print("  ✅ @mention text sent")
    except Exception as e:
        print(f"  ❌ @mention failed: {e}")
    # Then send card
    push(title, template, main_text, col_pairs, bottom_text, buttons)

def noon():
    """午盘 11:30"""
    idx = get_idx_quote()
    holdings = get_holdings()
    rows, total = holdings_block(holdings)

    send_mention_card(
        title=f"🌤️ 午盘{' 🟢' if total>=0 else ' 🔴'}",
        template="red" if total >= 0 else "green",
        main_text=f"浮盈 <font color=\"{'red' if total>=0 else 'green'}\">{'+' if total>=0 else ''}{total:.0f}元</font>\n**下午策略：** {'<font color=\"red\">持有等尾盘</font>' if total>=0 else '<font color=\"green\">破位走</font>'}",
        col_pairs=[
            ("📊 上午", f"{idx['p']}  {idx['c']:+.2f}%\n高 {idx['h']}  低 {idx['l']}"),
            ("🎯 下午", f"支撑 {idx['l']:.0f}\n压力 {max(idx['h'], idx['p']+15):.0f}"),
        ],
        bottom_text=f"### 👤 持仓\n{rows}" if rows else "",
        buttons=[("已操作 ✅", "primary", "act_alerts"), ("忽略 ⏸", "default", "ignore_card")]
    )

def close():
    """尾盘 14:50"""
    idx = get_idx_quote()
    holdings = get_holdings()
    rows, total = holdings_block(holdings)

    push(
        title=f"🌆 尾盘 {'🟢' if total>=0 else '🔴'}",
        template="red" if total >= 0 else "green",
        main_text=f"日终浮盈 <font color=\"{'red' if total>=0 else 'green'}\">{'+' if total>=0 else ''}{total:.0f}元</font>",
        col_pairs=[
            ("📊 全天", f"{idx['p']}  {idx['c']:+.2f}%\n开 {idx['o']}  高 {idx['h']}  低 {idx['l']}"),
            ("🎯 明日", f"支撑 {idx['l']:.0f}\n压力 {idx['h']:.0f}"),
        ],
        bottom_text=f"### 👤 持仓日终\n{rows}" if rows else "",
        buttons=[("已操作 ✅", "primary", "act_alerts"), ("忽略 ⏸", "default", "ignore_card")]
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: 盯盘小助手 morning|open5|open30|noon|close")
        sys.exit(1)
    mode = sys.argv[1]
    fn = {"morning": morning, "open5": open5, "open30": open30, "noon": noon, "close": close}.get(mode)
    if not fn: print(f"❌ 未知: {mode}"); sys.exit(1)
    print(f"🚀 盯盘小助手 [{mode}]")
    fn()
