#!/usr/bin/env python3
"""
Interaction callback handler for feishu card buttons.
Processes button clicks from alert cards.
Usage:
  python3 handle_interaction.py --status  (show pending)
  python3 handle_interaction.py <symbol> done|ignore|stop_done

Actions: done=已操作 | ignore=忽略 | stop_done=已止损
"""
import json, sys, re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/root/.openclaw/workspace/automation/stock-monitor")
PENDING_FILE = BASE_DIR / "pending_interaction.json"
WATCH_FILE = BASE_DIR / "stock_watch.py"
STATE_FILE = BASE_DIR / "alert_state.json"

def read_pending():
    try:
        return json.loads(PENDING_FILE.read_text())
    except:
        return []

def write_pending(items):
    PENDING_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2))

def show_status():
    pending = read_pending()
    active = [p for p in pending if p["status"] == "pending"]
    done = [p for p in pending if p["status"] != "pending"]
    print(f"Pending: {len(active)}, Done: {len(done)}")
    for p in active:
        print(f"  ⏳ [{p.get('symbol','?')}] {p.get('name','?')} @ {p.get('price','?')} - {p.get('label','?')}")
    for p in done:
        print(f"  {'✅' if p.get('status')=='done' else '⏸'} [{p.get('symbol','?')}] {p.get('name','?')} {p.get('status')}")

def handle_callback(symbol, action):
    pending = read_pending()
    matched = [p for p in pending if p["symbol"] == symbol and p["status"] == "pending"]
    if not matched:
        print(f"⚠️ No pending interaction for {symbol}")
        return False
    p = matched[0]
    name = p.get("name", symbol)
    for item in pending:
        if item["symbol"] == symbol and item["status"] == "pending":
            item["status"] = "done" if action in ("done", "stop_done") else "ignored"
            item["handled_at"] = datetime.now().strftime("%H:%M:%S")
    write_pending(pending)
    success = update_thresholds(symbol, action)
    print(f"{'✅' if success else '⚠️'} {name} ({symbol}): action={action}")
    return success

def update_thresholds(symbol, action):
    if not WATCH_FILE.exists():
        return False
    content = WATCH_FILE.read_text()
    modified = False
    if action == "done":
        old = content
        content = re.sub(r'"sell":\s*\[[^]]*\]', '"sell": [],  # 已操作', content)
        if content != old:
            modified = True
    if action == "stop_done":
        old = content
        content = re.sub(r'"sell":\s*\[[^]]*\]', '"sell": [],  # 已止损', content)
        content = re.sub(r'"buy":\s*\[[^]]*\]', '"buy": [],  # 已止损', content)
        if content != old:
            modified = True
    if modified:
        WATCH_FILE.write_text(content)
        try:
            STATE_FILE.write_text('{"last_alerts": {}}')
        except:
            pass
    return modified

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_status()
    elif len(sys.argv) == 3:
        handle_callback(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python3 handle_interaction.py --status")
        print("  or:  python3 handle_interaction.py <symbol> done|ignore|stop_done")
