#!/usr/bin/env python3
"""
统一行情数据引擎 v3
====================

数据源优先级（按稳定性调整）:

实时行情:
  ① Magpie   (本地, 快但偶发超时, timeout=1s)
  ② Tencent  (最稳, 该服务器上100%可用)
  ③ Sina     (备用)

日K线:
  ① Sina     (稳定, 带MA5/MA20)
  ② AKShare  (待网络恢复)
  ③ Tushare  (待积分到位)

60分钟K线:
  ① AKShare  (稳定时可用)
  ② 暂无可替代源

缓存策略:
  - 日K每日只拉1次, 缓存到.cache/kline_cache.json
  - 实时行情不缓存
"""

import json, os, time, requests
from pathlib import Path
from datetime import datetime, date

CACHE_DIR = Path("/root/.openclaw/workspace/automation/stock-monitor/.cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
KLIN_CACHE = CACHE_DIR / "kline_cache.json"
QUOTE_CACHE = CACHE_DIR / "quote_cache.json"

MAGPIE = "http://127.0.0.1:17891/api/v1/quotes"

# Magpie健康标记: 连续失败2次后跳过
_MAGPIE_FAILS = 0
_MAGPIE_SKIP = False

# ── 工具 ──

def now(): return datetime.now().strftime("%H:%M")
def today(): return date.today().isoformat()

def tc_code(code):
    """转为腾讯格式 sh601689"""
    if code.startswith("sh") or code.startswith("sz"):
        return code
    if code.startswith("6") or code.startswith("58"):
        return f"sh{code}"
    if code and code[0] in ("0", "3"):
        return f"sz{code}"
    return code


# ═══════════════════════════════════════════════════
#  1. 实时行情 (Magpie→Tencent→Sina)
# ═══════════════════════════════════════════════════

def get_quote(code):
    """实时行情, 返回 dict 或 None"""

    raw_code = code.replace("sh", "").replace("sz", "")

    global _MAGPIE_FAILS, _MAGPIE_SKIP

    # ① Magpie (首次健康时尝试, 连续2次失败后跳过)
    if not _MAGPIE_SKIP:
        try:
            import threading
            magpie_result = []
            def fetch_magpie():
                try:
                    r = requests.get(f"{MAGPIE}?codes={raw_code}", timeout=0.8)
                    if r.status_code == 200:
                        d = r.json()
                        if d.get("ok") and d.get("quotes"):
                            magpie_result.append(d["quotes"][0])
                except:
                    pass
            t = threading.Thread(target=fetch_magpie, daemon=True)
            t.start()
            t.join(timeout=0.8)
            if magpie_result:
                _MAGPIE_FAILS = 0
                q = magpie_result[0]
                return {
                    "price": q["price"],
                    "change_pct": q.get("changePct", 0),
                    "high": q.get("high", 0),
                    "low": q.get("low", 0),
                    "open": q.get("open", 0),
                    "prev_close": q.get("prevClose", 0),
                    "volume": q.get("volume", 0),
                    "turnover_rate": q.get("turnoverRate", 0),
                    "source": "magpie",
                }
            else:
                _MAGPIE_FAILS += 1
                if _MAGPIE_FAILS >= 2:
                    _MAGPIE_SKIP = True
        except:
            pass

    # ② Tencent (最稳主力)
    try:
        r = requests.get(f"http://qt.gtimg.cn/q={tc_code(code)}", timeout=5)
        r.encoding = "gbk"
        parts = r.text.strip().split("~")
        if len(parts) >= 40 and parts[3]:
            return {
                "price": float(parts[3]),
                "change_pct": float(parts[32]) if parts[32] else 0,
                "high": float(parts[33]) if parts[33] else 0,
                "low": float(parts[34]) if parts[34] else 0,
                "open": float(parts[5]) if parts[5] else 0,
                "prev_close": float(parts[4]) if parts[4] else 0,
                "volume": float(parts[6]) if parts[6] else 0,
                "turnover_rate": float(parts[38]) if parts[38] else 0,
                "source": "tencent",
            }
    except:
        pass

    # ③ Sina (最后防线)
    try:
        sc = tc_code(code)
        url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"CN_MarketData.getKLineData?symbol={sc}&scale=5&ma=1&datalen=1")
        r = requests.get(url, timeout=5)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            bar = data[-1]
            return {
                "price": float(bar["close"]),
                "change_pct": 0,
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "open": float(bar["open"]),
                "prev_close": 0,
                "volume": int(bar.get("volume", 0)),
                "turnover_rate": 0,
                "source": "sina",
            }
    except:
        pass

    return None


# ═══════════════════════════════════════════════════
#  2. 日K线 + 实时MA (Sina主力→Tushare备用)
# ═══════════════════════════════════════════════════

def _load_cache():
    if KLIN_CACHE.exists():
        try:
            return json.loads(KLIN_CACHE.read_text())
        except:
            pass
    return {}

def _save_cache(cache):
    KLIN_CACHE.write_text(json.dumps(cache))


def _sina_daily(code, days=25):
    """用Sina日K API拉数据"""
    sc = tc_code(code)
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={sc}&scale=240&ma=5,20&datalen={days}")
    r = requests.get(url, timeout=10)
    data = r.json()
    if isinstance(data, list) and len(data) >= days - 5:
        return {
            "closes": [float(d["close"]) for d in data],
            "ma5": float(data[-1].get("ma_price5", 0)),
            "ma20": float(data[-1].get("ma_price20", 0)),
            "bars": data,
            "source": "sina",
            "count": len(data),
        }
    return None


def _tushare_daily(code):
    """用Tushare拉日K (备用, 需积分)"""
    try:
        import tushare as ts
        ts.set_token('a039b2bbff5953b9398be45667d4547fcf4c9f7a737684092ba43514')
        pro = ts.pro_api()
        ts_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
        df = pro.daily(ts_code=ts_code, start_date="20260425")
        if df is not None and len(df) >= 20:
            closes = df["close"].tolist()[::-1]  # Tushare是倒序
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            return {
                "closes": closes,
                "ma5": round(ma5, 2),
                "ma20": round(ma20, 2),
                "source": "tushare",
                "count": len(closes),
            }
    except Exception as e:
        if "权限" in str(e):
            return {"error": "tushare需积分", "source": "tushare"}
    return None


def get_daily(code, force=False):
    """
    获取日K数据 (每天缓存1次)
    返回: {closes, ma5, ma20, source, ...}
    """
    cache = _load_cache()
    key = f"{code}_{today()}"

    if key not in cache or force:
        result = None

        # Sina 主力
        try:
            result = _sina_daily(code)
        except:
            pass

        # Tushare 备用 (记录错误但不阻塞)
        if not result:
            try:
                result = _tushare_daily(code)
            except:
                pass

        if result:
            cache[key] = result
            _save_cache(cache)
            return result

        # 用缓存中的旧数据兜底
        fallback_keys = [k for k in cache if k.startswith(code)]
        if fallback_keys:
            cache[key] = cache[fallback_keys[-1]]
            _save_cache(cache)
            return cache[key]

        return None

    return cache[key]


def get_live_ma(code, force=False):
    """
    实时MA5/MA20
    MA5 = (近4天收盘价总 + 今日现价) / 5
    MA20 = (近19天收盘价总 + 今日现价) / 20
    """
    daily = get_daily(code, force=force)
    if not daily or daily.get("error"):
        return None, None, None, None

    closes = daily["closes"]
    if len(closes) < 22:
        return None, None, None, None

    q = get_quote(code)
    if not q:
        return None, None, None, None

    tp = q["price"]

    ma5 = round((sum(closes[-4:]) + tp) / 5, 2)
    ma20 = round((sum(closes[-19:]) + tp) / 20, 2)

    detail = {
        "price": tp,
        "ma5": ma5,
        "ma20": ma20,
        "near_ma5_pct": round(abs(tp - ma5) / ma5 * 100, 2),
        "change_pct": q.get("change_pct", 0),
        "turnover_rate": q.get("turnover_rate", 0),
        "source": daily.get("source", "?"),
    }

    return ma5, ma20, tp, detail


# ═══════════════════════════════════════════════════
#  3. 60分钟K线 (短线分析)
# ═══════════════════════════════════════════════════

def get_hourly_bars(code, limit=20):
    """获取60分钟K线, 返回列表"""
    try:
        import akshare as ak
        import pandas as pd
        # 超时保护 - AKShare有时会卡住
        import threading
        result = []
        def fetch():
            try:
                df = ak.stock_zh_a_hist_min_em(
                    symbol=code, period="60",
                    start_date="20260501", end_date="20260522"
                )
                if df is not None and len(df) > 0:
                    result.append(df)
            except:
                pass
        t = threading.Thread(target=fetch, daemon=True)
        t.start()
        t.join(timeout=5)
        if result:
            df = result[0]
            df["收盘"] = df["收盘"].astype(float)
            return df.tail(limit).to_dict("records")
        return None
    except:
        pass
    return None


def analyze_hourly(code):
    """小时线分析: 支撑/压力/趋势"""
    bars = get_hourly_bars(code)
    if not bars:
        return None

    closes = [b["收盘"] for b in bars]
    highs = [b["最高"] for b in bars]
    lows = [b["最低"] for b in bars]
    cur = closes[-1]

    ma10 = round(sum(closes[-10:]) / 10, 2) if len(closes) >= 10 else round(sum(closes) / len(closes), 2)
    last4 = closes[-4:]
    trend = "↑" if last4[-1] > last4[0] else "↓" if last4[-1] < last4[0] else "→"

    return {
        "current": cur,
        "h20_high": max(highs),
        "h20_low": min(lows),
        "ma10": ma10,
        "trend": trend,
        "near_ma10_pct": round(abs(cur - ma10) / ma10 * 100, 2),
    }


# ═══════════════════════════════════════════════════
#  4. 一键分析
# ═══════════════════════════════════════════════════

def evaluate(code, name, force=False, hourly=True):
    """完整分析"""
    r = {"name": name, "code": code, "time": now()}

    q = get_quote(code)
    if q:
        r.update(q)

    ma5, ma20, _, det = get_live_ma(code, force=force)
    if det:
        r.update(det)

    if hourly:
        hr = analyze_hourly(code)
        if hr:
            r["hourly"] = hr

    # 评分
    score = 0
    price = r.get("price", 0)
    if price > 0 and ma20 and price > ma20: score += 3
    if det and det.get("near_ma5_pct", 99) < 1.0: score += 2
    elif det and det.get("near_ma5_pct", 99) < 1.5: score += 1
    hr = r.get("hourly")
    if hr:
        if hr["near_ma10_pct"] < 1.5: score += 2
        if hr["trend"] == "↑": score += 1
    if q and q.get("change_pct", 0) > 0: score += 1
    tr = r.get("turnover_rate", 0) or 0
    if tr > 10: score -= 2

    r["score"] = score
    return r


# ═══════════════════════════════════════════════════
#  5. 命令行
# ═══════════════════════════════════════════════════

def cmd_test():
    tests = [
        ("601689", "拓普集团"), ("300124", "汇川技术"),
        ("002892", "科力尔"),
        ("002241", "歌尔股份"), ("600879", "航天电子"),
        ("603019", "中科曙光"), ("600886", "国投电力"),
        ("600030", "中信证券"), ("601688", "华泰证券"),
    ]
    for code, name in tests:
        r = evaluate(code, name, hourly=False)
        print(f"{name:10s} 价:{r.get('price',0):>8.2f}  "
              f"MA5:{r.get('ma5',0):>8.2f}  MA20:{r.get('ma20',0):>8.2f}  "
              f"偏离5:{r.get('near_ma5_pct',0):>5.1f}%  "
              f"得分:{r.get('score',0)}  源:{r.get('source','?')}")
        sys.stdout.flush()


def cmd_detail(code, name):
    r = evaluate(code, name, force=True)
    print(f"\n=== {name}({code}) 完整分析 ===")
    src = r.get("source", "?")
    print(f"\n📊 实时行情 (数据源: {src})")
    for k in ["price", "change_pct", "high", "low", "open", "prev_close", "turnover_rate"]:
        v = r.get(k)
        if v is not None: print(f"  {k}: {v}")
    print(f"\n📈 日K均线 (来源: {src})")
    for k in ["ma5", "ma20", "near_ma5_pct"]:
        v = r.get(k)
        if v is not None: print(f"  {k}: {v}")
    hr = r.get("hourly")
    if hr:
        print(f"\n⏰ 60分钟K线")
        for k in ["current", "h20_high", "h20_low", "ma10", "trend", "near_ma10_pct"]:
            v = hr.get(k)
            if v is not None: print(f"  {k}: {v}")
    print(f"\n⭐ 综合评分: {r.get('score', 0)} / 10")


def cmd_clear():
    if KLIN_CACHE.exists():
        KLIN_CACHE.unlink()
        print("✅ 缓存已清空")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print("quote_engine.py <命令> [参数]")
        print("  test             批量检查")
        print("  detail <code> <name>  单股详细")
        print("  clear            清空缓存")
    elif args[0] == "test":
        cmd_test()
    elif args[0] == "clear":
        cmd_clear()
    elif args[0] == "detail" and len(args) >= 3:
        cmd_detail(args[1], args[2])
