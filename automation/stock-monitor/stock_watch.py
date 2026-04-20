#!/usr/bin/env python3
"""
A Stock Watcher - Eastmoney lightweight quote API
Monitors: 300456 (赛微电子) and 588000 (科创50ETF)
Trigger modes:
  - once:    fetch & print current data
  - watch:   fetch, check alerts, write to alerts.json
  - alerts:  print pending alerts
"""
import json, sys, time
from pathlib import Path

STOCKS = [
    ("0.300456", "赛微电子"),
    ("1.588000", "科创50ETF"),
    ("0.300346", "南大光电"),
]

STATE_FILE  = Path("/root/.openclaw/workspace/automation/stock-monitor/state.json")
ALERT_FILE  = Path("/root/.openclaw/workspace/automation/stock-monitor/alerts.json")

# ──────────────────────────────────────────────────────────────
# 买卖点阈值配置（由 @cx 根据基本面+技术面设置，2026-04-14）
# ──────────────────────────────────────────────────────────────
# 格式：symbol → {"buy": [(price_min, price_max, label)], "sell": [...], "stop": float}

THRESHOLDS = {
    "300456": {
        "name": "赛微电子",
        "pos": "已清仓",
        "sell": [],
        "buy": [],
        "stop": 0,
        "stop_label": "",
        "stop_msg":  "",
    },
    "588000": {
        "name": "科创50ETF",
        "pos": "0.6成仓",
        "sell": [
            (15.30, 15.40, "T出提醒①",  "昨高压力区，量价背离先走",),
            (15.50, 15.60, "T出提醒②",  "前期高点，强压区全清"),
        ],
        "buy": [
            (14.90, 15.00, "接回支撑①",  "昨收支撑，缩量回调买"),
            (14.70, 14.90, "接回支撑②",  "布林下轨，强支撑"),
        ],
        "stop": 14.50,
        "stop_label": "止损警戒",
        "stop_msg":  "⚠️ ETF跌破止损线！",
    },
    "300346": {
        "name": "南大光电",
        "pos": "1成仓（成本49.21）",
        "sell": [
            (50.50, 51.00, "T出提醒①",  "50心理关口，分批减",),
            (51.00, 52.00, "T出提醒②",  "前期强压力，拉升到位全清",),
        ],
        "buy": [
            (48.50, 49.00, "接回支撑①",  "昨收支撑，缩量回调买",),
            (47.00, 48.50, "接回支撑②",  "布林下轨，极限支撑",),
        ],
        "stop": 47.00,
        "stop_label": "止损警戒",
        "stop_msg":  "⚠️ 跌破成本线49.21，注意风控！",
    },
}

# Eastmoney field map (verified working):
# f43=current price(分), f44=open(分),  f45=prev_close(分)
# f46=high(分),   f47=low? (分, unreliable for some stocks)
# f48=volume?,   f50=amount?
# f58=name, f57=code, f169=change%(x100), f170=change_abs(分)


def fetch_quotes() -> list[dict]:
    import requests
    results = []
    for secid, name in STOCKS:
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        try:
            r = requests.get(url, params=params, timeout=8)
            r.raise_for_status()
            r.encoding = "utf-8"
            data = r.json()
            d = data.get("data", {})
            if not d:
                continue
            price     = round((d.get("f43") or 0) / 100, 2)
            prev      = round((d.get("f45") or 0) / 100, 2)
            chg_pct   = round((d.get("f169") or 0) / 100, 2)
            chg_abs   = round((d.get("f170") or 0) / 100, 2)
            results.append({
                "symbol":    d.get("f57", secid),
                "name":      d.get("f58", name),
                "price":     price,
                "open":      round((d.get("f44") or 0) / 100, 2),
                "prev_close": prev,
                "high":      round((d.get("f46") or 0) / 100, 2),
                "low":       price * 0.995,   # fallback
                "change_pct": chg_pct,
                "change_abs": chg_abs,
                "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception as e:
            print(f"Error {secid}: {e}", file=sys.stderr)
    return results


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def check_thresholds(data: dict, old: dict | None) -> list[dict]:
    sym   = data["symbol"]
    price = data["price"]
    alerts = []

    if sym not in THRESHOLDS:
        return alerts

    cfg = THRESHOLDS[sym]

    # ── Stop-loss (highest priority) ──────────────────────────
    stop = cfg["stop"]
    if stop and price <= stop:
        alerts.append({
            "type":   "stop_loss",
            "symbol": sym,
            "name":   cfg["name"],
            "price":  price,
            "threshold": stop,
            "label":  cfg["stop_label"],
            "message": f"{cfg['stop_msg']}\n「{cfg['name']}」现价 {price} ≤ 止损 {stop}",
        })
        return alerts   # stop-loss blocks other signals

    # ── Sell signals ───────────────────────────────────────────
    prev_sent_s = (old or {}).get("_sent_sell", [])
    for (lo, hi, label, reason) in cfg.get("sell", []):
        if lo <= price <= hi:
            if label not in prev_sent_s:
                alerts.append({
                    "type":      "sell_signal",
                    "symbol":    sym,
                    "name":      cfg["name"],
                    "price":     price,
                    "threshold": f"{lo}~{hi}",
                    "label":     label,
                    "reason":    reason,
                    "pos":       cfg["pos"],
                    "message": (
                        f"🔴 {label}\n"
                        f"「{cfg['name']}」({sym})\n"
                        f"现价: {price} | 触发区间: {lo}~{hi}\n"
                        f"📌 {reason}\n"
                        f"持仓: {cfg['pos']} | 建议: 分批T出"
                    ),
                })

    # ── Buy signals ───────────────────────────────────────────
    prev_sent_b = (old or {}).get("_sent_buy", [])
    for (lo, hi, label, reason) in cfg.get("buy", []):
        if lo <= price <= hi:
            if label not in prev_sent_b:
                alerts.append({
                    "type":      "buy_signal",
                    "symbol":    sym,
                    "name":      cfg["name"],
                    "price":     price,
                    "threshold": f"{lo}~{hi}",
                    "label":     label,
                    "reason":    reason,
                    "pos":       cfg["pos"],
                    "message": (
                        f"🟢 {label}\n"
                        f"「{cfg['name']}」({sym})\n"
                        f"现价: {price} | 触发区间: {lo}~{hi}\n"
                        f"📌 {reason}\n"
                        f"持仓: {cfg['pos']} | 建议: 回踩支撑接回"
                    ),
                })

    return alerts


def check_alerts(data: dict, old: dict | None) -> list[dict]:
    """Legacy ±2% threshold alert (lower priority)."""
    alerts = []
    pct     = data["change_pct"]
    old_pct = (old or {}).get("change_pct", 0)
    THRESHOLD = 2.0

    if abs(pct) >= THRESHOLD and abs(old_pct) < THRESHOLD:
        direction = "📈 上涨" if pct > 0 else "📉 下跌"
        alerts.append({
            "type":      "price_alert",
            "symbol":    data["symbol"],
            "name":      data["name"],
            "direction": direction,
            "price":     data["price"],
            "change_pct": pct,
            "message": (
                f"{direction} {THRESHOLD}% 阈值！\n"
                f"「{data['name']}」({data['symbol']})\n"
                f"现价: {data['price']} | 涨跌: {pct:+.2f}%\n"
                f"今开: {data['open']} | 最高: {data['high']}\n"
                f"⚠️ 触发提醒，结合买卖点自行判断"
            ),
        })

    if old and abs(pct) >= 0.5:
        if data["price"] >= data["high"] and data["high"] > data["open"]:
            alerts.append({
                "type":      "high_alert",
                "symbol":    data["symbol"],
                "name":      data["name"],
                "price":     data["price"],
                "change_pct": pct,
                "message":   f"🔺 新高 {data['name']} {data['price']}（{pct:+.2f}%）",
            })

    return alerts


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"

    if mode == "once":
        results = fetch_quotes()
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    elif mode == "watch":
        old_state = load_state()
        new_state = {}
        all_alerts = []

        for data in fetch_quotes():
            sym = data["symbol"]
            new_state[sym] = data

            # 1) Custom 买卖点 thresholds (priority)
            thresh_alerts = check_thresholds(data, old_state.get(sym))
            # 2) Legacy ±2% / 新高 alerts
            pct_alerts    = check_alerts(data, old_state.get(sym))
            all_alerts.extend(thresh_alerts)
            all_alerts.extend(pct_alerts)

            # Remember what we already sent so we don't spam the same label
            if thresh_alerts:
                new_state[sym]["_sent_sell"] = [a["label"] for a in thresh_alerts if a["type"] == "sell_signal"]
                new_state[sym]["_sent_buy"]  = [a["label"] for a in thresh_alerts if a["type"] == "buy_signal"]
            else:
                new_state[sym]["_sent_sell"] = old_state.get(sym, {}).get("_sent_sell", [])
                new_state[sym]["_sent_buy"]  = old_state.get(sym, {}).get("_sent_buy", [])

        save_state(new_state)

        if all_alerts:
            ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
            ALERT_FILE.write_text(json.dumps(all_alerts, indent=2, ensure_ascii=False))
            for a in all_alerts:
                print(f"ALERT: [{a['type']}] {a['message']}")
        else:
            print("no_alerts")

    elif mode == "alerts":
        if ALERT_FILE.exists():
            print(ALERT_FILE.read_text())
        else:
            print("[]")


if __name__ == "__main__":
    main()
