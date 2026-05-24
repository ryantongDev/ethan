#!/usr/bin/env python3
"""
Runs stock_watch.py watch mode with deduplication.
- Same alert for same stock: only pushes ONCE per 15min cooldown
- Re-alerts if price moves >2%
- Writes to Feishu shared file for on-demand analysis
"""
import subprocess, json, sys, os, time, urllib.request
from pathlib import Path
from datetime import datetime

# Button interaction system
PENDING_MODULE = "/root/.openclaw/workspace/automation/stock-monitor/pending_interaction.py"

SCRIPT       = "/root/.openclaw/workspace/automation/stock-monitor/stock_watch.py"
ALERT_FILE   = Path("/root/.openclaw/workspace/automation/stock-monitor/alerts.json")
STATE_FILE   = Path("/root/.openclaw/workspace/automation/stock-monitor/alert_state.json")
FEISHU_FILE  = Path("/root/.openclaw/workspace/knowledge-base/今日盯盘告警.json")
NODE_PATH    = "/root/.nvm/versions/node/v22.22.2/bin/node"
WAKE_SCRIPT  = "/root/.openclaw/workspace/automation/stock-monitor/wake_cx.js"

COOLDOWN_MINUTES = 2
PRICE_MOVE_PCT   = 1.0


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
    elapsed = (now - last["time"]) / 60
    if elapsed >= COOLDOWN_MINUTES:
        price_change = abs(price - last["price"]) / max(last["price"], 0.01) * 100
        if price_change >= PRICE_MOVE_PCT:
            return True
        return False
    return False


def build_feishu_card(alerts):
    """Build execution-focused Feishu card matching new template"""
    all_sell = all("卖" in a.get("type", "") for a in alerts)
    all_buy  = all("买" in a.get("type", "") for a in alerts)
    template = "green" if all_buy else "red"

    cards = []
    for a in alerts:
        name   = a.get("name", "?")
        symbol = a.get("symbol", "?")
        price  = a.get("price", 0)
        atype  = a.get("type", "?")
        label  = a.get("label", "")

        conclusion   = a.get("conclusion", f"{atype}，执行纪律")
        trigger_sig  = a.get("trigger_signal", label)
        sell_range   = a.get("sell_range", "—")
        buy_range    = a.get("buy_range", "—")
        stop_loss    = a.get("stop_loss", "—")
        pos_action   = a.get("position_action", "—")
        reason       = a.get("reason", "触发纪律信号")
        discipline   = a.get("discipline_note", "卖飞不可怕，坐电梯才伤。")
        change_pct   = a.get("change_pct", "—")

        range_display = buy_range if "买" in atype else sell_range
        range_label   = "买入区间" if "买" in atype else "卖出区间"

        content = (
            f"**【执行结论】**\n{conclusion}\n\n"
            f"### 🎯 执行区间\n"
            f"**股票：** {name} ({symbol})\n"
            f"**最新价：** {price} | **涨跌幅：** {change_pct}%\n\n"
            f"📈 **触发信号：** {trigger_sig}\n\n"
            f"**{range_label}：** {range_display}\n"
            f"**失效/止损价：** {stop_loss}\n"
            f"**仓位动作：** {pos_action}\n\n"
            f"### 📖 为什么\n{reason}\n\n"
            f"⚠️ **老张盯你一句：**\n*{discipline}*"
        )

        sym = symbol
        actions = [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": f"✅ {name} 执行"},
                "type": "primary" if all_sell else "danger",
                "value": {"command": f"act_{sym}_{atype}"}
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": f"⏸ {name} 忽略"},
                "type": "default",
                "value": {"command": f"ign_{sym}_{atype}"}
            }
        ]

        elements = [
            {"tag": "markdown", "content": content},
            {"tag": "hr"},
            {"tag": "action", "actions": actions},
            {"tag": "hr"},
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"⏰ {datetime.now().strftime('%H:%M:%S')} · 点击按钮自动执行 · 仅供参考，不构成投资建议"
            }]}
        ]

        cards.append({
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True, "enable_forward": True},
                "header": {
                    "title": {"tag": "plain_text",
                               "content": f"🚨 {'买入' if '买' in atype else '卖出'}执行提醒 · {name}"},
                    "template": template
                },
                "elements": elements
            }
        })
    return cards


def push_to_feishu(alerts):
    """Push decisive execution-focused cards directly to this feishu group"""
    if not alerts:
        return False

    cards = build_feishu_card(alerts)

    for payload in cards:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(FEISHU_WEBHOOK, data=data,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            print(f"  ✅ Feishu push OK: {payload['card']['header']['title']['content']}")
        except Exception as e:
            print(f"  ❌ Feishu push failed: {e}")
            return False
    return True


def write_feishu_alerts(alerts):
    try:
        FEISHU_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(alerts),
            "alerts": []
        }
        for a in alerts:
            payload["alerts"].append({
                "name": a.get("name", "?"),
                "symbol": a.get("symbol", "?"),
                "price": a.get("price", 0),
                "type": a.get("type", "?"),
                "label": a.get("label", ""),
                "pos": a.get("pos", "")
            })
        FEISHU_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"  ✅ Feishu alerts written: {len(alerts)}")
        return True
    except Exception as e:
        print(f"  ❌ Feishu write error: {e}")
        return False


def main():
    r = subprocess.run(["python3", SCRIPT, "watch"], capture_output=True, text=True, timeout=30)
    if r.stderr:
        print(r.stderr[:500], file=sys.stderr)

    alerts = []
    if ALERT_FILE.exists():
        try:
            alerts = json.loads(ALERT_FILE.read_text())
        except Exception:
            alerts = []

    write_feishu_alerts(alerts)

    if not alerts:
        print("No alerts this cycle.")
        return

    new_alerts = [a for a in alerts if is_new_alert(a, load_state())]

    if not new_alerts:
        print(f"Suppressed {len(alerts)} alerts (in cooldown).")
        return

    print(f"NEW alerts ({len(new_alerts)}/{len(alerts)}):")
    for a in new_alerts:
        print(f"  [{a.get('type','?')}] {a.get('name','?')} {a.get('price','?')} — {a.get('label','?')}")

    pushed = push_to_feishu(new_alerts)

    # Write pending interactions for button cards
    if new_alerts:
        try:
            subprocess.run(["python3", PENDING_MODULE], capture_output=True, timeout=10)
            # Write pending file
            pending_data = []
            for a in new_alerts:
                pending_data.append({
                    "id": f"{a.get('symbol','?')}_{a.get('type','?')}_{time.time():.0f}",
                    "symbol": a.get("symbol", ""),
                    "name": a.get("name", ""),
                    "price": a.get("price", 0),
                    "type": a.get("type", ""),
                    "label": a.get("label", ""),
                    "pos": a.get("pos", ""),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "status": "pending",
                })
            pending_path = Path("/root/.openclaw/workspace/automation/stock-monitor/pending_interaction.json")
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            pending_path.write_text(json.dumps(pending_data, ensure_ascii=False, indent=2))
            print(f"  ✅ Pending interactions written: {len(pending_data)}")
        except Exception as e:
            print(f"  ❌ Pending write error: {e}")

    # Update state
    state = load_state()
    now = time.time()
    for a in alerts:
        key = f"{a.get('symbol','?')}:{a.get('type','?')}:{a.get('label','?')}"
        state["last_alerts"][key] = {
            "time": now, "price": a.get("price", 0),
            "type": a.get("type","?"), "label": a.get("label",""),
            "pushed": pushed
        }
    stale = [k for k, v in state["last_alerts"].items() if (now - v["time"]) / 60 > 120]
    for k in stale:
        del state["last_alerts"][k]
    save_state(state)

    if pushed:
        print(f"✅ Feishu 已推送 {len(new_alerts)} 条买卖点信号")
    else:
        print("⚠️ 推送失败")


if __name__ == "__main__":
    main()
