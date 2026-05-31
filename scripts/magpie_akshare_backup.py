#!/usr/bin/env python3
"""
Magpie AKShare Backup Data Source
每5分钟运行一次，获取全量行情数据存入本地 JSON
当 Magpie 数据源失效时，Agent 自动切到本文件
"""
import json
import os
import sys
from datetime import datetime

DATA_DIR = os.path.expanduser("~/.magpie")
BACKUP_FILE = os.path.join(DATA_DIR, "akshare_backup.json")
EXPIRE_SECONDS = 300  # 5分钟

def fetch_data():
    """从 akshare 获取全量监控行情"""
    try:
        import akshare as ak
    except ImportError:
        print("akshare not installed, skipping")
        return None

    stocks = [
        # 用户持仓
        "300124"  # 汇川技术,  # 汇川技术
        "300496",  # 中科创达
        "002892",  # 科力尔
        "588000",  # 科创50ETF
        "000001",  # 上证指数
        # 原有自选
        "600519", "000858", "000333", "601899", "600036",
        "000001", "300750", "002415", "688981", "603986",
        "300782", "002371", "601138", "300308", "002463",
        "600941", "601728",
    ]

    data = {}
    # 批量获取实时行情
    try:
        df = ak.stock_zh_a_spot_em()
        for _, row in df.iterrows():
            code = row.get("代码", "")
            if code in stocks or not stocks:
                data[code] = {
                    "name": row.get("名称", ""),
                    "price": row.get("最新价", 0),
                    "change": row.get("涨跌额", 0),
                    "change_pct": row.get("涨跌幅", 0),
                    "volume": row.get("成交量", 0),
                    "amount": row.get("成交额", 0),
                    "high": row.get("最高", 0),
                    "low": row.get("最低", 0),
                    "open": row.get("今开", 0),
                    "prev_close": row.get("昨收", 0),
                    "turnover": row.get("换手率", 0),
                    "pe": row.get("市盈率-动态", 0),
                    "market_cap": row.get("总市值", 0),
                }
    except Exception as e:
        print(f"AKShare fetch error: {e}")
        return None

    result = {
        "timestamp": datetime.now().isoformat(),
        "source": "akshare",
        "stocks": data,
    }
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
