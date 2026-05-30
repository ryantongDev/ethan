#!/usr/bin/env python3
"""
盯盘小助手 v2 — 动态实时监控
每10秒拉一次数据，检查持仓关键位，触发条件自动推送

使用MiniMax M2.7处理数据（包月不计费）
"""
import json
import time
import urllib.request
import ssl
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

# === 配置 ===
TZ = timezone(timedelta(hours=8))
CHECK_INTERVAL = 10  # 10秒

# 老张持仓（实时更新）
POSITIONS = {
    "002600": {"name": "领益智造", "cost": 15.737, "shares": 500, "sold": 400, "sold_at": 15.02},
    "002892": {"name": "科力尔", "cost": 11.805, "shares": 500, "sold": 500, "sold_at": 11.13},
    "300124": {"name": "汇川技术", "cost": 78.561, "shares": 300, "sold": 0, "sold_at": 0},
}

# 预警阈值
ALERT_CONFIG = {
    "002600": {"alert_low": 14.50, "alert_high": 16.00, "ma_periods": 20},
    "002892": {"alert_low": 10.80, "alert_high": 11.50, "ma_periods": 20},
    "300124": {"alert_low": 74.50, "alert_high": 78.00, "ma_periods": 20},
}

# 飞书群推送
WEBHOOK_URL = ""  # 需要配飞书webhook或者通过openclaw推送

# 状态跟踪
last_alert = {}  # 每个股票的最近提醒时间，避免重复推送
last_prices = {}  # 上次价格

# 市场时间判断
def is_market_open():
    """判断A股是否在交易时间"""
    now = datetime.now(TZ)
    # 9:30 - 11:30, 13:00 - 15:00
    if now.weekday() >= 5:  # 周末
        return False
    t = now.hour * 60 + now.minute
    return (9*60+30 <= t <= 11*60+30) or (13*60 <= t <= 15*60)

def fetch_quotes():
    """拉取实时行情"""
    codes = ",".join([f"sz{s}" for s in POSITIONS.keys()])
    url = f"https://web.sqt.gtimg.cn/q=sh000001,sz399001,{codes}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode("gbk")
        return data
    except Exception as e:
        return None

def parse_quote(data, code):
    """从返回数据中解析指定股票"""
    for line in data.strip().split("\n"):
        if f"v_sz{code}" in line or f"v_sh{code}" in line:
            parts = line.split("~")
            if len(parts) > 33:
                return {
                    "name": parts[1],
                    "code": parts[2],
                    "price": float(parts[3]),
                    "yclose": float(parts[4]) if parts[4] else 0,
                    "open": float(parts[5]),
                    "high": float(parts[33]),
                    "low": float(parts[34]),
                    "volume": int(parts[6]) if parts[6] else 0,
                    "change_pct": float(parts[32]) if parts[32] else 0,
                }
    return None

def check_alerts(code, quote):
    """检查是否触发预警"""
    now = time.time()
    pos = POSITIONS[code]
    config = ALERT_CONFIG[code]
    price = quote["price"]
    cost = pos["cost"]
    
    alerts = []
    
    # 1. 跌破防线
    if price < config["alert_low"]:
        key = f"{code}_low_{config['alert_low']}"
        if key not in last_alert or (now - last_alert[key]) > 120:  # 每2分钟提醒一次
            alerts.append(f"🚨 {pos['name']}跌破{config['alert_low']}防线！当前{price:.2f}")
            last_alert[key] = now
    
    # 2. 冲高到卖点
    if price > config["alert_high"]:
        key = f"{code}_high_{config['alert_high']}"
        if key not in last_alert or (now - last_alert[key]) > 120:
            pnl = (price - cost) * pos["shares"]
            alerts.append(f"📤 {pos['name']}冲到{config['alert_high']}以上！当前{price:.2f}，建议减仓")
            last_alert[key] = now
    
    # 3. 急速下跌（5秒内跌超过2%）
    if code in last_prices and last_prices[code] > 0:
        drop_pct = (price - last_prices[code]) / last_prices[code] * 100
        if drop_pct < -1.5:  # 跌超1.5%
            key = f"{code}_flashdrop"
            if key not in last_alert or (now - last_alert[key]) > 300:  # 5分钟冷却
                alerts.append(f"⚡ {pos['name']}急速下跌{drop_pct:.1f}%！({last_prices[code]:.2f}→{price:.2f})")
                last_alert[key] = now
    
    # 4. 盈亏比例检查
    pnl_pct = (price - cost) / cost * 100
    if pnl_pct < -8 and pos["shares"] > 0:
        key = f"{code}_pctl_{int(pnl_pct)}"
        if key not in last_alert or (now - last_alert[key]) > 600:  # 10分钟冷却
            alerts.append(f"🔴 {pos['name']}浮亏已达{pnl_pct:.1f}%，建议考虑止损")
            last_alert[key] = now
    
    # 记录价格
    last_prices[code] = price
    
    return alerts

def push_alert(message):
    """推送预警到飞书群"""
    # 通过openclaw发送消息到飞书群
    # 使用message命令
    cmd = [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", "chat:oc_8eb8a6d7127a1828331123cee9b3eb92",
        "--message", message
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception as e:
        print(f"Push error: {e}")

def get_index_status():
    """获取大盘状态"""
    codes = "sh000001,sz399001"
    url = f"https://web.sqt.gtimg.cn/q={codes}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode("gbk")
        result = {}
        for line in data.strip().split("\n"):
            parts = line.split("~")
            if len(parts) > 32:
                name = parts[1]
                price = parts[3]
                chg = parts[32]
                result[name] = f"{price}({chg}%)"
        return result
    except:
        return {}

def main():
    print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] 盯盘小助手v2启动")
    print(f"持仓: {', '.join([f'{v[\"name\"]}({v[\"shares\"]}股)' for k,v in POSITIONS.items()])}")
    print(f"每{CHECK_INTERVAL}秒扫描一次")
    print("=" * 50)
    
    silent_count = 0
    startup = True
    
    while True:
        if not is_market_open():
            if not startup:
                time.sleep(60)  # 非交易时间60秒检查一次
                continue
            else:
                startup = False
        
        quote_data = fetch_quotes()
        
        if quote_data:
            all_alerts = []
            index_status = get_index_status()
            
            for code in POSITIONS:
                quote = parse_quote(quote_data, code)
                if quote:
                    alerts = check_alerts(code, quote)
                    all_alerts.extend(alerts)
            
            if all_alerts:
                # 有预警，立即推送
                msg = f"[盯盘{datetime.now(TZ).strftime('%H:%M:%S')}]"
                if index_status:
                    idx_str = " | ".join([f"{k}{v}" for k,v in index_status.items()])
                    msg += f"\n{idx_str}"
                for a in all_alerts:
                    msg += f"\n{a}"
                print(f"\n[{datetime.now(TZ).strftime('%H:%M:%S')}] 🚨 触发预警:")
                print(msg)
                push_alert(msg)
                silent_count = 0
            else:
                silent_count += 1
                # 每50次检查（约8分钟）打印一次状态
                if silent_count % 50 == 0:
                    status_parts = []
                    for code in POSITIONS:
                        quote = parse_quote(quote_data, code)
                        if quote:
                            pos = POSITIONS[code]
                            pnl = (quote["price"] - pos["cost"]) * pos["shares"]
                            status_parts.append(f"{pos['name']}:{quote['price']:.2f}")
                    print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] 正常 | {' '.join(status_parts)}")
        else:
            print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] 数据获取失败")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
