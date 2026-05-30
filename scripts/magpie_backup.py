#!/usr/bin/env python3
"""
Magpie 备用行情数据源 (Tencent API)
每5分钟运行一次，获取全量行情数据存入本地 JSON
当 Magpie 数据源失效时，Agent 自动切到本文件
"""
import json
import os
import sys
import requests
from datetime import datetime

DATA_DIR = os.path.expanduser("~/.magpie")
BACKUP_FILE = os.path.join(DATA_DIR, "backup_quotes.json")
EXPIRE_SECONDS = 300  # 5分钟

STOCKS = [
    # === 用户持仓 ===
    "sz300124",  # 汇川技术
    "sz300496",  # 中科创达  (actually 300496 is SZ)
    "sz002892",  # 科力尔
    "sh588000",  # 科创50ETF
    "sh000001",  # 上证指数
    # === 大盘/指数 ===
    # 原有自选
    # 消费/白酒
    "sh600519", "sz000858",
    # 金融
    "sz000001", "sh600036",
    # 新能源
    "sz300750",
    # 科技/半导体
    "sh688981", "sh603986", "sz300782", "sz002371",
    # AI/算力
    "sh601138", "sz300308", "sz002463",
    # 通信
    "sh600941", "sh601728",
    # 其他
    "sz000333", "sh601899", "sz002415",
]

def format_stock_code(code):
    """Convert sh/sz code format for Tencent API"""
    return code

def fetch_data():
    """从腾讯API获取行情"""
    codes = ",".join(STOCKS)
    url = f"https://qt.gtimg.cn/q={codes}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get(url, timeout=10)
        r.encoding = "gbk"
        lines = r.text.strip().split("\n")
    except Exception as e:
        print(f"Tencent API error: {e}")
        return None

    data = {}
    for line in lines:
        parts = line.split("~")
        if len(parts) < 44:
            continue
        code_raw = parts[0].split("_")[-1] if "_" in parts[0] else ""
        name = parts[1]
        price = parts[3]
        prev_close = parts[4]
        change = parts[31]
        change_pct = parts[32]
        volume = parts[6]
        amount = parts[37]
        high = parts[33]
        low = parts[34]
        open_price = parts[5]
        turnover = parts[38]
        pe = parts[39]
        market_cap = parts[44] if len(parts) > 44 else ""
        
        data[code_raw] = {
            "name": name,
            "price": float(price) if price and price != "0.00" else 0,
            "change": float(change) if change else 0,
            "change_pct": float(change_pct) if change_pct else 0,
            "volume": float(volume) if volume else 0,
            "amount": float(amount) if amount else 0,
            "high": float(high) if high else 0,
            "low": float(low) if low else 0,
            "open": float(open_price) if open_price else 0,
            "prev_close": float(prev_close) if prev_close else 0,
            "turnover": float(turnover) if turnover and turnover != "-" else 0,
            "pe": float(pe) if pe and pe != "-" else 0,
            "market_cap": float(market_cap) if market_cap and market_cap != "-" else 0,
        }

    result = {
        "timestamp": datetime.now().isoformat(),
        "source": "tencent",
        "stocks": data,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BACKUP_FILE, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Backup saved: {len(data)} stocks at {result['timestamp']}")
    return result

def load_backup():
    """Agent 过来读取备用数据"""
    if not os.path.exists(BACKUP_FILE):
        return None
    with open(BACKUP_FILE) as f:
        data = json.load(f)
    age = (datetime.now() - datetime.fromisoformat(data["timestamp"])).total_seconds()
    if age > EXPIRE_SECONDS:
        print(f"Backup expired ({age:.0f}s > {EXPIRE_SECONDS}s)")
        return None
    return data

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--load":
        data = load_backup()
        if data:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print("{}")
    else:
        fetch_data()
