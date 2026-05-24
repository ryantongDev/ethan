#!/usr/bin/env python3
"""
A Stock Watcher - Eastmoney lightweight quote API
Monitors user's holdings and watchlist.
Modes:
  - once:    fetch & print current data
  - watch:   fetch, check alerts, write to alerts.json
"""
import json, sys, time, re
from pathlib import Path
from datetime import datetime, timedelta

# ── 用户持仓 + 掌柜关注板块 ──
STOCKS = [
    # 持仓
    ("0.300496", "中科创达"),
    ("0.300124", "汇川技术"),
    ("0.002892", "科力尔"),
    ("1.588000", "科创50ETF"),
    ("1.000001", "上证指数"),
    # 算力
    ("1.603019", "中科曙光"),
    ("0.300308", "中际旭创"),
    # 无人驾驶
    ("1.601689", "拓普集团"),
    # 商业航天
    ("1.600879", "航天电子"),
    ("1.600118", "中国卫星"),
    # 消费电子
    ("0.002241", "歌尔股份"),
    ("1.601138", "工业富联"),
    # 工业母机
    ("0.002008", "大族激光"),
    # 电力
    ("1.600900", "长江电力"),
    ("1.600886", "国投电力"),
    # PCB+消费电子
    ("0.002600", "领益智造"),
    # 保险
    ("1.601318", "中国平安"),
    ("1.601601", "中国太保"),
    # 券商
    ("1.600030", "中信证券"),
    ("1.601688", "华泰证券"),
]

STATE_FILE = Path("/root/.openclaw/workspace/automation/stock-monitor/state.json")
ALERT_FILE = Path("/root/.openclaw/workspace/automation/stock-monitor/alerts.json")
FEISHU_FILE = Path("/root/.openclaw/workspace/knowledge-base/今日盯盘状态.json")

# ── 买卖点阈值（区间交易法）──
# 原则：提前预警，给区间，在区间内自由操作
THRESHOLDS = {
    "300496": {
        "name": "中科创达",
        "cost": 66.29,
        "pos": "已清仓(止盈+7.5%)，等接回",
        "sell": [],
        "buy": [
            (68.00, 69.00, "📥买入: 68~69", "买入区间到了，买100股"),
        ],
    },
    "300124": {
        "name": "汇川技术",
        "cost": 77.41,
        "pos": "已T100股→78.8, 剩100股",
        "sell": [
            (79.50, 80.00, "📤卖出: 79.5~80", "剩余仓位止盈"),
        ],
        "buy": [
            (76.00, 76.50, "📥买入: 76~76.5", "接回T出的仓位"),
        ],
        "stop": 75.00,
        "stop_label": "🚨跌破75清仓",
    },
    "002892": {
        "name": "科力尔",
        "cost": 11.40,
        "pos": "800股@11.40",
        "sell": [
            (11.75, 11.95, "📤卖出: 11.75~11.95", "卖出区间到了，减400股"),
        ],
        "buy": [
            (11.00, 11.20, "📥买入: 11~11.2", "买入区间到了，接400股"),
        ],
        "stop": 10.80,
        "stop_label": "🚨跌破10.8清仓",
    },
    "000001": {
        "name": "上证指数",
        "cost": 0,
        "pos": "大盘监控",
        "sell": [
            (4095, 4105, "📤卖出: 4095~4105", "修复到位了，可以减"),
            (4180, 4200, "📤卖出: 4180~4200", "掌柜压力位，必须减"),
        ],
        "buy": [
            (4040, 4050, "📥买入: 4040~4050", "掌柜说的强支撑，到了介入"),
        ],
        "stop": 4030,
        "stop_label": "🚨大盘破4030清仓",
    },
    "601689": {
        "name": "拓普集团",
        "cost": 0,
        "pos": "观察-等待买入",
        "sell": [
            (73.50, 74.50, "📤卖出: 73.5~74.5", "接近前高74.68，到了先T出"),
        ],
        "buy": [
            (68.50, 70.00, "📥买入: 68.5~70", "回踩到MA5下方，买入区间"),
        ],
        "stop": 64.00,
        "stop_label": "🚨跌破MA20(64)止损",
    },
    "002600": {
        "name": "领益智造",
        "cost": 0,
        "pos": "观察-等待回踩买入",
        "sell": [
            (16.80, 17.00, "📤卖出: 16.8~17", "接近前高17.07止盈"),
        ],
        "buy": [
            (15.60, 16.00, "📥买入: 15.6~16", "回踩MA5附近或以下低吸"),
        ],
        "stop": 14.80,
        "stop_label": "🚨破14.8出局",
    },
    "588000": {
        "name": "科创50ETF",
        "cost": 1.86,
        "pos": "已清仓(2500→1.891), 等回踩",
        "sell": [],
        "buy": [
            (1.820, 1.850, "📥买入: 1.82~1.85", "回踩接回"),
        ],
        "stop": 1.800,
        "stop_label": "🚨跌破1.8清仓",
    },
}


# ── 行情API（Tencent - 稳定版）──
def get_quotes():
    """Fetch quotes via Tencent API, return {clean_code: {data}}"""
    # Map stock tuples to Tencent codes: sh600xxx or sz300xxx
    def to_tencent_code(stock):
        stock_code = stock[0]  # e.g. "0.300496"
        if stock_code.startswith("0."):
            return f"sz{stock_code[2:]}"  # sz300496
        elif stock_code.startswith("1."):
            return f"sh{stock_code[2:]}"  # sh588000
        return f"sh{stock_code}"
    
    import requests
    codes_list = [to_tencent_code(s) for s in STOCKS]
    codes_str = ",".join(codes_list)
    url = f"http://qt.gtimg.cn/q={codes_str}"
    try:
        r = requests.get(url, timeout=10)
        r.encoding = "gbk"
        raw = r.text
    except Exception as e:
        print(f"  ❌ API error: {e}")
        return {}

    result = {}
    for line in raw.strip().split("\n"):
        parts = line.split("~")
        if len(parts) < 38:
            continue
        code_raw = parts[2]  # Tencent format: field index 2 is the stock code
        if not code_raw:
            continue
        price_str = parts[3]
        if not price_str or price_str == "0.00":
            continue
        result[code_raw] = {
            "name": parts[1],
            "price": float(price_str),
            "change_pct": float(parts[32]) if parts[32] else 0,
            "change_price": float(parts[31]) if parts[31] else 0,
        }
    return result


def check_alerts(code, price, quote=None):
    """Check if price triggers any threshold alert"""
    alerts = []
    clean_code = code.replace("sz", "").replace("sh", "")
    if clean_code not in THRESHOLDS:
        return alerts

    cfg = THRESHOLDS[clean_code]
    stop = cfg.get("stop")

    # Stop loss check
    if stop and price > 0 and price <= stop:
        alerts.append({
            "symbol": code, "name": cfg["name"], "price": price,
            "type": "🚨止损",
            "label": cfg["stop_label"],
            "pos": cfg.get("pos", ""),
            "change_pct": quote.get("change_pct", "—") if quote else "—",
            "conclusion": "止损执行，不等反弹",
            "trigger_signal": "价格触及止损价，触发止损条件",
            "sell_range": f"≤{price:.2f}",
            "buy_range": "—",
            "stop_loss": f"{price:.2f}（已触发）",
            "position_action": "立即清仓，不拖延",
            "reason": "价格跌至止损价，纪律优先，不抱幻想",
            "discipline_note": "止损是保护，不是失败。知行合一。",
        })
        return alerts

    # Sell signals
    for sell_range in cfg.get("sell", []):
        low, high, label, msg = sell_range
        if low and high and low <= price <= high:
            alerts.append({
                "symbol": code, "name": cfg["name"], "price": price,
                "type": "📤卖出信号",
                "label": f"{label} | {msg}",
                "pos": cfg.get("pos", ""),
                "change_pct": quote.get("change_pct", "—") if quote else "—",
                "conclusion": "卖出区间已到，执行纪律",
                "trigger_signal": label,
                "sell_range": f"{low:.2f} ~ {high:.2f}",
                "buy_range": "—",
                "stop_loss": cfg.get("stop", "—"),
                "position_action": msg,
                "reason": "价格进入卖出区间，卖在计划内就是合格，不追求最高点",
                "discipline_note": "卖飞不可怕，坐电梯才伤。先卖。",
            })

    # Buy signals
    for buy_range in cfg.get("buy", []):
        low, high, label, msg = buy_range
        if low and high and low <= price <= high:
            alerts.append({
                "symbol": code, "name": cfg["name"], "price": price,
                "type": "📥买入信号",
                "label": f"{label} | {msg}",
                "pos": cfg.get("pos", ""),
                "change_pct": quote.get("change_pct", "—") if quote else "—",
                "conclusion": "买入区间已到，试错执行",
                "trigger_signal": label,
                "sell_range": "—",
                "buy_range": f"{low:.2f} ~ {high:.2f}",
                "stop_loss": cfg.get("stop", "—"),
                "position_action": msg,
                "reason": "价格进入买入区间，等待信号确认，小仓介入",
                "discipline_note": "买入信号不是满仓理由，先试错，错了立刻走。",
            })

    return alerts



def get_market_status():
    """Determine if market is open"""
    now = datetime.now()
    if now.weekday() >= 5:
        return "休市（周末）"
    t = now.time()
    open_time = datetime.strptime("09:30", "%H:%M").time()
    close_time = datetime.strptime("15:00", "%H:%M").time()
    noon_start = datetime.strptime("11:30", "%H:%M").time()
    noon_end = datetime.strptime("13:00", "%H:%M").time()
    if t < open_time:
        return "未开盘"
    elif t < noon_start:
        return "交易中"
    elif t < noon_end:
        return "午间休市"
    elif t < close_time:
        return "交易中"
    else:
        return "已收盘"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    show_title = mode == "once"

    quotes = get_quotes()
    lines = []
    all_alerts = []

    for stock_code, stock_name in STOCKS:
        clean_code = re.sub(r'^[01]\.', '', stock_code)
        q = quotes.get(clean_code)

        if show_title:
            print(f"  ", end="")

        if not q or not q.get("price") or q["price"] == 0:
            print(f"  ⏳ {stock_name}: 获取中...")
            continue

        price = q["price"]
        change = q.get("change_pct", "")

        # Check alerts
        alerts = check_alerts(clean_code, price, q)
        if alerts:
            all_alerts.extend(alerts)
            alert_types = [a["type"] for a in alerts]
            status = f"🚨 {' '.join(alert_types)}"
        else:
            status = "无信号"

        cfg = THRESHOLDS.get(clean_code, {})
        cost = cfg.get("cost", 0)
        pnl_pct = round((price - cost) / cost * 100, 2) if cost > 0 else None
        risk = "⚠️" if (cfg.get("stop") and price <= cfg["stop"] * 1.02) else "✅"

        print(f"  {'🚨' if alerts else '✅'} {stock_name}: {price} → [{status}]")

        if mode == "watch":
            lines.append({
                "name": stock_name, "code": clean_code, "price": price,
                "cost": cost, "pnl_pct": pnl_pct,
                "stop": cfg.get("stop", None), "risk": risk
            })

    if mode == "watch":
        # Write alerts
        if all_alerts:
            ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
            ALERT_FILE.write_text(json.dumps(all_alerts, ensure_ascii=False, indent=2))
            print(f"\n✅ {len(all_alerts)}个信号触发")
        else:
            ALERT_FILE.write_text("[]")
            print("\n✅ 无触发信号的买卖点")

        # Write shared status file
        watch_status = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_status": get_market_status(),
            "stocks": lines,
            "alerts": all_alerts,
        }
        FEISHU_FILE.parent.mkdir(parents=True, exist_ok=True)
        FEISHU_FILE.write_text(json.dumps(watch_status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
