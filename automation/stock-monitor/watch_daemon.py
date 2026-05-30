#!/usr/bin/env python3
"""
Fast polling daemon: checks alerts every 5 seconds.
Runs as background process (not cron-based).
"""
import subprocess, json, sys, os, time, urllib.request
from pathlib import Path
from datetime import datetime

SCRIPT       = "/root/.openclaw/workspace/automation/stock-monitor/stock_watch.py"
ALERT_FILE   = Path("/root/.openclaw/workspace/automation/stock-monitor/alerts.json")
STATE_FILE   = Path("/root/.openclaw/workspace/automation/stock-monitor/alert_state.json")
LOG_FILE     = Path("/var/log/stock_daemon.log")

COOLDOWN_SEC  = 60   # 60秒内不重复推送（比cron的2分钟更短）
PRICE_MOVE_PCT = 0.5  # 价格变动0.5%以上就重新推送
POLL_INTERVAL  = 5    # 5秒轮询

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(line + "\n", mode="a")
    except:
        pass

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return {"last_alerts": {}}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def is_new_alert(a, state):
    now = time.time()
    symbol = a.get("symbol", "?")
    alert_type = a.get("type", "?")
    price = a.get("price", 0)
    label = a.get("label", "")
    key = f"{symbol}:{alert_type}:{label}"
    last = state["last_alerts"].get(key)
    if last is None:
        return True
    elapsed = now - last.get("time", 0)
    if elapsed < COOLDOWN_SEC:
        return False
    price_change = abs(price - last.get("price", 0)) / max(last.get("price", 0.01), 0.01) * 100
    if price_change >= PRICE_MOVE_PCT:
        return True
    return False

def send_mention_text(name):
    """Send text message with @mention to trigger this bot"""
    MY_ID = "ou_e3f9c80f19f1c38f8d5e53b3a78879d5"
    LAOZHANG_ID = "ou_0e554d5177c5cedbf66573e7e5d2f038"
    try:
        text_payload = {
            "msg_type": "text",
            "content": {"text": f"<at user_id=\"{MY_ID}\">小G</at> 盯盘信号触发 [{name}]，请帮我分析！"}
        }
        data = json.dumps(text_payload).encode("utf-8")
        req = urllib.request.Request("https://open.feishu.cn/open-apis/bot/v2/hook/dec20a90-d24b-42d0-8f55-c77e2e37c818", data=data,
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        log(f"  ✅ @mention text sent for {name}")
    except Exception as e:
        log(f"  ❌ @mention failed: {e}")

def push_to_feishu(alerts):
    """Push Feishu card via webhook"""
    if not alerts:
        return False
    # Send @mention text first
    send_mention_text(alerts[0].get('name','?'))
    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True, "enable_forward": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"🚨 快速盯盘信号 · {alerts[0].get('name','?')}"},
                    "template": "red" if "卖" in alerts[0].get("type","") else "green"
                },
                "elements": [{"tag": "markdown", "content": build_content(alerts)}]
            }
        }
        data = json.dumps(payload).encode("utf-8")
        # 使用飞书机器人webhook（需要配置）
        req = urllib.request.Request("https://open.feishu.cn/open-apis/bot/v2/hook/dec20a90-d24b-42d0-8f55-c77e2e37c818", data=data,
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        log(f"Feishu push failed: {e}")
        return False

def build_content(alerts):
    lines = []
    # Card内部不用@（不生效），直接写小G
    lines.append("小G 盯盘信号已触发，请帮我分析：")
    for a in alerts:
        name = a.get("name","?")
        price = a.get("price",0)
        atype = a.get("type","?")
        label = a.get("label","")
        sell = a.get("sell_range","—")
        buy = a.get("buy_range","—")
        stop = a.get("stop_loss","—")
        reason = a.get("reason","")
        discipline = a.get("discipline_note","")
        range_txt = buy if "买" in atype else sell
        range_lbl = "买入区间" if "买" in atype else "卖出区间"
        win = a.get("win_rate",0)
        lines.append(f"**【{atype}】** {name} @{price}\n"
                     f"触发：{label}\n"
                     f"**{range_lbl}：** {range_txt}\n"
                     f"止损：{stop} | 胜率：{win}%\n"
                     f"原因：{reason}\n"
                     f"⚠️ {discipline}\n")
    return "\n---\n".join(lines)

def check_alerts():
    """Fetch latest prices and check against alerts"""
    r = subprocess.run(["python3", SCRIPT, "watch"], capture_output=True, text=True, timeout=30)
    if r.stderr:
        print(r.stderr[:300], file=sys.stderr)
    
    if not ALERT_FILE.exists():
        return []
    try:
        alerts = json.loads(ALERT_FILE.read_text())
    except:
        return []
    return alerts

def main():
    log("🚀 Fast poll daemon started (5s interval)")
    log(f"Cooldown: {COOLDOWN_SEC}s | Price move: >{PRICE_MOVE_PCT}%")
    
    while True:
        try:
            alerts = check_alerts()
            if not alerts:
                time.sleep(POLL_INTERVAL)
                continue
            
            state = load_state()
            new_alerts = [a for a in alerts if is_new_alert(a, state)]
            
            if new_alerts:
                log(f"🟢 NEW: {[a.get('name') for a in new_alerts]}")
                for a in new_alerts:
                    log(f"   {a.get('type')} {a.get('name')} @ {a.get('price')} — {a.get('label')}")
                pushed = push_to_feishu(new_alerts)
                
                now = time.time()
                for a in alerts:
                    key = f"{a.get('symbol','?')}:{a.get('type','?')}:{a.get('label','?')}"
                    state["last_alerts"][key] = {
                        "time": now, "price": a.get("price",0),
                        "type": a.get("type","?"), "label": a.get("label","")
                    }
                save_state(state)
                log(f"   Push {'OK' if pushed else 'FAILED'}")
            else:
                log(f"⏳ {len(alerts)} alerts in cooldown")
            
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            log("⏹ Daemon stopped")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
