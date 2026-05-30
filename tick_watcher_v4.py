#!/usr/bin/env python3
"""
盯盘小助手 v4 — 直接用飞书webhook推送
Webhook: https://open.feishu.cn/open-apis/bot/v2/hook/dec20a90-d24b-42d0-8f55-c77e2e37c818
使用MiniMax M2.7处理（包月不计费）
"""
import json
import time
import urllib.request
import ssl
import os
import sys
from datetime import datetime, timezone, timedelta

# === 配置 ===
TZ = timezone(timedelta(hours=8))
CHECK_INTERVAL = 15  # 15秒扫一次
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dec20a90-d24b-42d0-8f55-c77e2e37c818"

# 老张持仓（最新）
POSITIONS = {
    "002600": {"name": "领益智造", "cost": 15.737, "shares": 500},
    "002892": {"name": "科力尔", "cost": 11.805, "shares": 500},
    "300124": {"name": "汇川技术", "cost": 78.561, "shares": 300},
}

# 防线配置
ALERT_LOW = {"002600": 14.50, "002892": 10.80, "300124": 74.50}
ALERT_HIGH = {"002600": 16.00, "002892": 11.50, "300124": 78.00}
STOP_LOSS_PCT = -8.0

# 状态追踪
last_prices = {}
alert_cooldown = {}
COOLDOWN = 120  # 2分钟冷却

def is_market_open():
    now = datetime.now(TZ)
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return (9*60+30 <= t <= 11*60+30) or (13*60 <= t <= 15*00)

def fetch_all():
    """拉实时行情（Tencent API）"""
    codes = "sh000001,sz399001,sz002600,sz002892,sz300124"
    url = f"https://web.sqt.gtimg.cn/q={codes}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.read().decode("gbk")
    except Exception as e:
        print(f"[FETCH ERROR] {e}")
        return None

def parse(data, code):
    for line in data.strip().split("\n"):
        if line.startswith(f"v_sz{code}") or line.startswith(f"v_sh{code}"):
            parts = line.split("~")
            if len(parts) > 34:
                try:
                    return {
                        "price": float(parts[3]),
                        "yclose": float(parts[4]) if parts[4].replace('.','',1).lstrip('-').isdigit() else 0,
                        "open": float(parts[5]),
                        "high": float(parts[33]),
                        "low": float(parts[34]),
                        "volume": int(parts[6]) if parts[6].isdigit() else 0,
                        "change_pct": float(parts[32]) if parts[32].replace('.','',1).lstrip('-').isdigit() else 0,
                    }
                except:
                    return None
    return None

def send_webhook(msg):
    """通过飞书webhook推送消息"""
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": msg}
    }).encode("utf-8")
    
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("code") == 0:
            print(f"[SENT] {msg[:60]}...")
            return True
        else:
            print(f"[WEBHOOK ERROR] {result}")
            return False
    except Exception as e:
        print(f"[SEND ERROR] {e}")
        return False

def check_and_alert(code, quote, pos):
    now = time.time()
    price = quote["price"]
    cost = pos["cost"]
    name = pos["name"]
    pnl_pct = (price - cost) / cost * 100
    
    alerts = []
    
    # 1. 跌破防线
    low = ALERT_LOW[code]
    if price < low:
        key = f"{code}_low"
        if key not in alert_cooldown or (now - alert_cooldown[key]) > COOLDOWN:
            alerts.append(f"🚨 {name} 跌破{low}防线！当前{price:.2f}，浮亏{pnl_pct:.1f}%")
            alert_cooldown[key] = now
    
    # 2. 高抛窗口
    high = ALERT_HIGH[code]
    if price > high:
        key = f"{code}_high"
        if key not in alert_cooldown or (now - alert_cooldown[key]) > COOLDOWN:
            alerts.append(f"📤 {name} 冲到{high}以上！当前{price:.2f}，建议减仓")
            alert_cooldown[key] = now
    
    # 3. 止损线 -8%
    if pnl_pct < STOP_LOSS_PCT:
        key = f"{code}_stoploss"
        if key not in alert_cooldown or (now - alert_cooldown[key]) > 600:
            alerts.append(f"🔴 {name} 浮亏{pnl_pct:.1f}%，成本{cost}现价{price:.2f}，建议止损")
            alert_cooldown[key] = now
    
    # 4. 急速下跌
    if code in last_prices and last_prices[code] > 0:
        drop = (price - last_prices[code]) / last_prices[code] * 100
        if drop < -1.5:
            key = f"{code}_flash_{int(price*100)}"
            if key not in alert_cooldown or (now - alert_cooldown[key]) > 180:
                alerts.append(f"⚡ {name} 急跌！{last_prices[code]:.2f}→{price:.2f}（{-drop:.1f}%）")
                alert_cooldown[key] = now
    
    # 5. 开盘7分钟内高抛窗口
    now_dt = datetime.now(TZ)
    market_minutes = (now_dt.hour - 9) * 60 + now_dt.minute
    if 30 <= market_minutes <= 37:
        yclose = quote["yclose"]
        if yclose > 0 and price > yclose * 1.01:
            key = f"{code}_open7_{now_dt.strftime('%Y%m%d')}"
            if key not in alert_cooldown:
                alerts.append(f"🕐 {name} 高开{price:.2f}（>昨收+1%），高抛窗口！")
                alert_cooldown[key] = now
    
    last_prices[code] = price
    return alerts

def main():
    print(f"🚀 盯盘小助手 v4 启动")
    print(f"📌 持仓: {', '.join([f'{v[\"name\"]}({v[\"shares\"]}股)' for v in POSITIONS.values()])}")
    print(f"⏱  每{CHECK_INTERVAL}秒扫描")
    print(f"📢 推送到飞书webhook")
    print(f"📅 {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 启动时发一条测试消息
    test_msg = f"🤖 盯盘小助手已启动\n📌 {', '.join([f'{v[\"name\"]}({v[\"shares\"]}股)' for v in POSITIONS.values()])}\n⏱ 每{CHECK_INTERVAL}秒扫描"
    send_webhook(test_msg)
    
    cycle = 0
    
    while True:
        if not is_market_open():
            time.sleep(60)
            continue
        
        cycle += 1
        raw = fetch_all()
        
        if raw:
            try:
                sh = parse(raw, "000001")
                sz = parse(raw, "399001")
                sh_str = f"{sh['price']:.0f}({sh['change_pct']:+.1f}%)" if sh else "N/A"
                sz_str = f"{sz['price']:.0f}({sz['change_pct']:+.1f}%)" if sz else "N/A"
            except:
                sh_str, sz_str = "N/A", "N/A"
            
            all_alerts = []
            for code, pos in POSITIONS.items():
                quote = parse(raw, code)
                if quote:
                    alerts = check_and_alert(code, quote, pos)
                    all_alerts.extend(alerts)
            
            if all_alerts:
                now_str = datetime.now(TZ).strftime("%H:%M:%S")
                msg = f"📊 [{now_str}] 上证{sh_str} 深证{sz_str}\n"
                for a in all_alerts:
                    msg += f"{a}\n"
                print(f"\n[{now_str}] 🚨 触发预警!")
                print(msg)
                send_webhook(msg.strip())
            elif cycle % 40 == 0:
                status = []
                for code, pos in POSITIONS.items():
                    q = parse(raw, code)
                    if q:
                        pnl = (q["price"] - pos["cost"]) / pos["cost"] * 100
                        flag = "🔴" if pnl < -5 else ("🟢" if pnl > 0 else "🟡")
                        status.append(f"{pos['name']}{q['price']:.2f}({pnl:+.1f}%)")
                print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] ✅ 正常 | {' | '.join(status)}")
        else:
            print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] ⚠️ 数据获取失败")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
