#!/usr/bin/env python3
"""
Pending interaction manager for button-based stock alerts.
When the cron detects a signal, it writes pending interactions here.
The AI picks them up and sends interactive cards with buttons.
Button callbacks are handled to update stock_watch.py config.
"""
import json, os
from pathlib import Path
from datetime import datetime

PENDING_FILE = Path("/root/.openclaw/workspace/automation/stock-monitor/pending_interaction.json")
WATCH_FILE = Path("/root/.openclaw/workspace/automation/stock-monitor/stock_watch.py")

def write_pending(alerts):
    """Write pending alerts that need user interaction"""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    pending = []
    for a in alerts:
        pending.append({
            "id": f"{a.get('symbol','?')}_{a.get('type','?')}_{datetime.now().timestamp():.0f}",
            "symbol": a.get("symbol", ""),
            "name": a.get("name", ""),
            "price": a.get("price", 0),
            "type": a.get("type", ""),
            "label": a.get("label", ""),
            "pos": a.get("pos", ""),
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": "pending",  # pending | done | ignored
        })
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
    return pending


def read_pending():
    """Read current pending interactions"""
    try:
        return json.loads(PENDING_FILE.read_text())
    except:
        return []


def mark_done(symbol, action):
    """Mark a pending interaction as done (user acted)"""
    pending = read_pending()
    new_pending = []
    for p in pending:
        if p["symbol"] == symbol and p["status"] == "pending":
            p["status"] = "done" if action == "act" else "ignored"
            p["handled_at"] = datetime.now().strftime("%H:%M:%S")
        new_pending.append(p)
    PENDING_FILE.write_text(json.dumps(new_pending, ensure_ascii=False, indent=2))
    return [p for p in new_pending if p["status"] == "pending"]


def update_stock_config(symbol, action, price=None):
    """
    Update stock_watch.py THRESHOLDS based on user action.
    action: 'sold' | 'bought' | 'stop_executed'
    """
    # Read current config
    if not WATCH_FILE.exists():
        return False
    
    # Read file content
    content = WATCH_FILE.read_text()
    
    # Simple replacements based on action and symbol
    # (We do this by manipulating Python dict - but since it's embedded in Python source,
    #  we need string manipulation)
    
    if action == "sold":
        # Remove sell alerts, keep only buy alerts for re-entry
        # We look for the stock's sell section and empty it
        import re
        # Find stock section
        patterns = {
            "300496": (r'"300496":\s*\{.*?"stop_label":\s*"[^"]*",', None),
            "300124": (r'"300124":\s*\{.*?"stop_label":\s*"[^"]*",', None),
            "002892": (r'"002892":\s*\{.*?"stop_label":\s*"[^"]*",', None),
            "588000": (r'"588000":\s*\{.*?"stop_label":\s*"[^"]*",', None),
        }
        
        if symbol in patterns:
            # Set sells to empty, add "已操作" note
            pos_note = "已卖出，等接回"
            content = content.replace(f'"pos": "', f'"pos": "{pos_note} (已操作) ')
            # Replace sell section to empty
            content = re.sub(r'"sell":\s*\[[^\]]*\]', '"sell": []', content)
            WATCH_FILE.write_text(content)
            return True
    
    elif action == "bought":
        # Remove buy alerts, add sell alerts for profit-taking
        content = re.sub(r'"buy":\s*\[[^\]]*\]', '"buy": []', content)
        WATCH_FILE.write_text(content)
        return True
    
    elif action == "stop_executed":
        # Remove both buy and sell, mark as 已止损
        content = re.sub(r'"sell":\s*\[[^\]]*\]', '"sell": []', content)
        content = re.sub(r'"buy":\s*\[[^\]]*\]', '"buy": []', content)
        WATCH_FILE.write_text(content)
        return True
    
    return False


def build_button_card(pending_item):
    """Build a Feishu interactive card with action buttons"""
    symbol = pending_item["symbol"]
    name = pending_item["name"]
    price = pending_item["price"]
    atype = pending_item["type"]
    label = pending_item["label"]
    
    color = "red"
    if "买入" in atype:
        color = "green"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🚨 {name} {atype}"},
            "template": color
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{name} ({symbol})** 当前价: **{price}**\n{label}"
                }
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 已操作"},
                        "type": "primary",
                        "value": {"symbol": symbol, "action": "done"}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "⏸ 忽略此信号"},
                        "type": "default",
                        "value": {"symbol": symbol, "action": "ignore"}
                    }
                ]
            }
        ]
    }
    
    # For sell signals, add a third "已止损" button
    if "止损" in atype or "止损" in label:
        card["elements"][2]["actions"].insert(1, {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🚨 已止损执行"},
            "type": "danger",
            "value": {"symbol": symbol, "action": "stop_done"}
        })
    
    return card


if __name__ == "__main__":
    # Test: read pending and print
    pending = read_pending()
    print(f"Pending: {len(pending)}")
    for p in pending:
        print(f"  [{p['status']}] {p['name']} {p['price']} - {p['label']}")


# ── 追加: 批量操作 ──

def clear_all_pending():
    """已操作所有待处理"""
    pending = read_pending()
    for p in pending:
        if p["status"] == "pending":
            p["status"] = "done"
            p["handled_at"] = datetime.now().strftime("%H:%M:%S")
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
    return len(pending)


def ignore_all():
    """忽略所有待处理"""
    pending = read_pending()
    for p in pending:
        if p["status"] == "pending":
            p["status"] = "ignored"
            p["handled_at"] = datetime.now().strftime("%H:%M:%S")
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
    return len(pending)
