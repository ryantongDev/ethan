#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from datetime import datetime

STATE_DIR = Path('/root/.openclaw/workspace/state/task-workflows')
STATE_DIR.mkdir(parents=True, exist_ok=True)


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def save_state(task_id, data):
    path = STATE_DIR / f'{task_id}.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def load_state(task_id):
    path = STATE_DIR / f'{task_id}.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return None


def send_discord(channel_id, message):
    cmd = [
        'python3', '-c',
        (
            "from functions import message\n"
            f"print('Use OpenClaw message tool from chat runtime; external script placeholder for channel {channel_id}')"
        )
    ]
    subprocess.run(cmd, check=False)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)

    init_p = sub.add_parser('init')
    init_p.add_argument('--task-id', required=True)
    init_p.add_argument('--title', required=True)
    init_p.add_argument('--channel-id', required=True)
    init_p.add_argument('--status', default='进行中')
    init_p.add_argument('--summary', default='')

    step_p = sub.add_parser('step')
    step_p.add_argument('--task-id', required=True)
    step_p.add_argument('--status', required=True)
    step_p.add_argument('--message', required=True)

    show_p = sub.add_parser('show')
    show_p.add_argument('--task-id', required=True)

    args = parser.parse_args()

    if args.cmd == 'init':
        data = {
            'task_id': args.task_id,
            'title': args.title,
            'channel_id': args.channel_id,
            'status': args.status,
            'summary': args.summary,
            'history': [
                {'time': now_str(), 'status': args.status, 'message': args.summary}
            ]
        }
        path = save_state(args.task_id, data)
        print(path)
        return

    if args.cmd == 'step':
        data = load_state(args.task_id)
        if not data:
            raise SystemExit('task not found')
        data['status'] = args.status
        data['history'].append({'time': now_str(), 'status': args.status, 'message': args.message})
        save_state(args.task_id, data)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if args.cmd == 'show':
        data = load_state(args.task_id)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return


if __name__ == '__main__':
    main()
