#!/usr/bin/env python3
"""
A股持仓实时监控脚本
持仓: 588000, 科力尔(002892), 汇川技术(300124), 中科创达(300496)
"""
import json
import requests
import time
from datetime import datetime, timedelta

# 腾讯股票接口
STOCKS = {
    "002892": {"code": "sz002892", "name": "科力尔"},
    "300124": {"code": "sz300124", "name": "汇川技术"},
}

# ETF十大重仓关注
ETF_TOP_HOLDINGS = [
    "688981", "688012", "688036", "688008", "688111",
    "688256", "688122", "688396", "688303", "688005"
]

# 掌柜关注板块代表股
SECTOR_WATCH = {
    "算力": ["603019", "300308", "688041"],
    "机器人": ["300124", "002892", "688160"],
    "无人驾驶": ["300496", "002920", "601689"],
    "商业航天": ["600879", "600118"],
    "消费电子": ["002241", "601138"],
    "工业母机": ["300124", "002008"],
    "电力": ["600900", "600886"],
    "半导体(减仓观望)": ["688981", "002371"],
    "保险": ["601318", "601601"],
    "券商": ["600030", "601688"],
}

def fetch_quote(code):
    """获取实时行情"""
    url = f"http://qt.gtimg.cn/q={code}"
    try:
        r = requests.get(url, timeout=5)
        r.encoding = "gbk"
        text = r.text.strip()
        # 格式: v_sh000001="1,,name,price,涨跌,涨跌幅%..."
        if "=" in text and '"' in text:
            data = text.split('"')[1].split('~')
            if len(data) >= 33:
                return {
                    "name": data[1],
                    "price": float(data[3]) if data[3] else 0,
                    "change": float(data[31]) if data[31] else 0,
                    "change_pct": float(data[32]) if data[32] else 0,
                    "high": float(data[33]) if data[33] else 0,
                    "low": float(data[34]) if data[34] else 0,
                    "volume": float(data[6]) if data[6] else 0,  # 手
                    "amount": float(data[37]) if data[37] else 0,  # 万
                    "turnover": data[38] if len(data) > 38 else "",  # 换手率
                }
    except Exception as e:
        return {"error": str(e)}
    return None


def fetch_kline(code, days=5):
    """获取K线数据(简版)"""
    url = f"http://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},m5,,{days}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return data
    except:
        return None


def get_shenwan_concept(name):
    """模拟申万行业分类"""
    concepts = {
        "002892": "机器人/电机",
        "300124": "工业自动化/机器人",
        "300496": "智能汽车/操作系统",
        "588000": "科创板/半导体+AI",
    }
    return concepts.get(name, "")


def monitor():
    print(f"=== 📊 A股持仓实时监控 ===")
    print(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. 持仓监控
    print("【🏦 当前持仓】")
    print(f"{'代码':<10} {'名称':<16} {'现价':<10} {'涨跌幅':<10} {'最高':<10} {'最低':<10} {'状态'}")
    print("-" * 80)

    alerts = []
    for key, info in STOCKS.items():
        quote = fetch_quote(info["code"])
        if quote and "price" in quote:
            pct = quote["change_pct"]
            status = "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")
            print(f"{key:<10} {quote['name']:<16} {quote['price']:<10.3f} {pct:+.2f}%{'':<6} {quote['high']:<10.3f} {quote['low']:<10.3f} {status}")

            # 生成预警
            if pct < -3:
                alerts.append(f"🚨 {quote['name']}({key}) 跌幅 {pct:.1f}%，注意支撑！")
            elif pct > 5:
                alerts.append(f"📤 {quote['name']}({key}) 涨幅 {pct:.1f}%，注意反T机会！")
        else:
            print(f"{key:<10} {'获取失败':<16}")

    print()

    # 2. 板块监控（关键代表股）
    print("【📌 掌柜关注板块 - 代表股监控】")
    print(f"{'板块':<12} {'代码':<10} {'现价':<10} {'涨跌幅':<10} {'信号'}")
    print("-" * 60)

    for sector, codes in SECTOR_WATCH.items():
        for scode in codes:
            s_code = f"sz{scode}" if scode.startswith("00") or scode.startswith("30") else f"sh{scode}"
            scode_key = f"sh{scode}" if scode.startswith("60") or scode.startswith("68") else f"sz{scode}"
            quote = fetch_quote(scode_key)
            if quote and "price" in quote and quote["price"] > 0:
                pct = quote["change_pct"]
                signal = ""
                if pct > 2:
                    signal = "⚡率先修复"
                elif pct < -2:
                    signal = "⬇️继续调整"
                else:
                    signal = "⏸️整理中"
                print(f"{sector:<12} {scode:<10} {quote['price']:<10.2f} {pct:+.2f}%{'':<6} {signal}")

    print()

    # 3. 提醒
    if alerts:
        print("【⚠️ 实时提醒】")
        for a in alerts:
            print(a)
        print()

    # 4. 大盘信号
    print("【📐 大盘参考】")
    sh_quote = fetch_quote("sh000001")
    if sh_quote:
        print(f"上证指数: {sh_quote['price']:.2f} ({sh_quote['change_pct']:+.2f}%)")
    print()

    print("=" * 50)
    print("💡 今日策略参考:")
    print("  • 修复看量：放量站稳4100→看4130(5日线)")
    print("  • 修复不足/缩量：等尾盘再考虑")
    print("  • 强支撑：4030-4050")
    print("  • 方向：算力/机器人/无人驾驶/商业航天 谁先放量修复跟谁")
    print("=" * 50)


if __name__ == "__main__":
    monitor()
