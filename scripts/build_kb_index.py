#!/usr/bin/env python3
"""
知识库结构化整理脚本
调用 MiniMax (via okaoi API) 提取知识卡片，生成索引文件
"""

import os, sys, json, re, time
from pathlib import Path
import requests

API_KEY = "sk-c9df73f8555f12faaeeea13d4d79241899dd56396a6f29bff5dab33d81139436"
BASE_URL = "https://www.okaoi.com"
MODEL = "MiniMax-M2.7"

KB_ROOT = Path("/root/.openclaw/workspace/knowledge-base")
INDEX_DIR = Path("/root/.openclaw/workspace/knowledge_index")
PROMPT_FILE = Path("/root/.openclaw/workspace/prompts/minimax-kb-card-extractor.md")

INDEX_DIR.mkdir(parents=True, exist_ok=True)
prompt_template = open(PROMPT_FILE).read()


def call_minimax(prompt, retries=3):
    """Call MiniMax via okaoi API"""
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=120,
                verify=False,
            )
            if resp.status_code != 200:
                print(f"  ⚠️  HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
                if attempt < retries - 1:
                    time.sleep(3)
                    continue
                return None
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(5)
    return None


def parse_json(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse: {e}", file=sys.stderr)
        return None


def extract_card(file_path, section_title=None, section_content=None):
    source_path = str(file_path.relative_to(KB_ROOT))
    if section_content:
        content = section_content
        title = section_title or source_path
        card_id = f"{source_path}::{title}"
    else:
        content = open(file_path).read()
        title = section_title or file_path.stem
        card_id = source_path

    prompt = prompt_template.replace("{{source_path}}", source_path)
    prompt = prompt.replace("{{markdown_content}}", content)

    print(f"  📤 Calling MiniMax ({len(prompt)} chars)...", end=" ", flush=True)
    t0 = time.time()
    raw = call_minimax(prompt)
    elapsed = time.time() - t0
    if not raw:
        print("❌ (no response)")
        return None

    card = parse_json(raw)
    if not card:
        print(f"⚠️  (parse failed) took {elapsed:.0f}s")
        print(f"     raw start: {raw[:300]}")
        return None

    print(f"✅ ({elapsed:.0f}s)")
    card["id"] = card_id
    card["source_path"] = source_path
    if not card.get("title"):
        card["title"] = title
    return card


def split_book(file_path):
    """Split 金融笔记知识库-完整版.md by chapters"""
    content = open(file_path).read()
    lines = content.split('\n')

    # Extract TOC chapter list
    toc_chapters = []
    in_toc = False
    for line in lines:
        if "📑 目录" in line or "目录" in line:
            in_toc = True
            continue
        if in_toc and re.match(r'^\|.*\|$', line):
            m = re.match(r'^\|\s*(\d+[\d-]*)\s*\|\s*(.+?)\s*\|$', line)
            if m:
                toc_chapters.append((m.group(1).strip(), m.group(2).strip()))
        if in_toc and '|' not in line and line.strip() and len(line) > 5:
            in_toc = False

    if not toc_chapters:
        print("  ❌ Could not extract TOC")
        return []

    print(f"  📑 Found {len(toc_chapters)} chapters in TOC")

    # Find each chapter's position in the document
    # Pattern: ## 🔖 01 盈在看盘·盘口基础  or ### 01. Title
    sections = []
    chapter_positions = []

    for num, title in toc_chapters:
        found_pos = None
        for i, line in enumerate(lines):
            # Match: ## 🔖 01 盈在看盘·盘口基础  or ## 🔖 01 ...
            if re.match(rf'^##\s+🔖\s*{re.escape(num)}\s', line):
                found_pos = i
                break
            # Match: ## 01. 盈在 or ## 01 盈在
            if re.match(rf'^##\s+#?\s*{re.escape(num)}(\.|、|：|:|\s)', line):
                found_pos = i
                break
            # Match: just the number in a heading
            if re.match(r'^##\s', line) and re.search(rf'\b{re.escape(num)}\b', line) and title[:4] in line:
                found_pos = i
                break

        if found_pos is not None:
            chapter_positions.append((num, title, found_pos))

    # Sort by position
    chapter_positions.sort(key=lambda x: x[2])

    # Extract content between chapters
    for idx, (num, title, pos) in enumerate(chapter_positions):
        if idx < len(chapter_positions) - 1:
            end_pos = chapter_positions[idx + 1][2]
        else:
            end_pos = len(lines)
        content_section = '\n'.join(lines[pos:end_pos]).strip()
        if len(content_section) > 100:
            sections.append((f"{num}. {title}", content_section))

    # If sections too short, try a simpler approach: split by ## headers
    if len(sections) < 10:
        print(f"  ⚠️  Only got {len(sections)} sections, retrying with ## split...")
        sections = []
        current_title = None
        current_lines = []
        for line in lines:
            if re.match(r'^##\s+\d', line):
                if current_title and current_lines:
                    sections.append((current_title, '\n'.join(current_lines)))
                current_title = line.lstrip('#').strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_title and current_lines:
            sections.append((current_title, '\n'.join(current_lines)))

    return sections


def main():
    cards_path = INDEX_DIR / "cards.json"
    existing_cards = {}
    if cards_path.exists():
        try:
            for c in json.load(open(cards_path)):
                existing_cards[c["id"]] = c
            print(f"📂 Loaded {len(existing_cards)} existing cards (resume mode)")
        except:
            pass

    md_files = sorted(KB_ROOT.glob("*.md"))
    print(f"📁 Found {len(md_files)} .md files")

    all_cards = list(existing_cards.values())
    failed = []

    # === Phase 1: Small files first ===
    small_files = [f for f in md_files if f.name not in ("金融笔记知识库-完整版.md",)]
    for file_path in small_files:
        fname = file_path.name
        print(f"\n{'='*50}\n📄 {fname}")

        if fname in ("今日盘前思路.md", "今日午盘思路.md", "a股操盘手频道知识库.md"):
            print("  ⏭️  Skip (dynamic/index)")
            continue

        source_id = str(file_path.relative_to(KB_ROOT))
        if source_id in existing_cards:
            print("  ⏭️  Already done")
            continue

        card = extract_card(file_path)
        if card:
            all_cards.append(card)
            json.dump(all_cards, open(cards_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            print(f"  🏷️  {card.get('primary_category','?')} | {card.get('one_sentence','')[:50]}")
        else:
            failed.append({"file": fname})
            print("  ❌ Failed")

    # === Phase 2: Big book ===
    big_book = KB_ROOT / "金融笔记知识库-完整版.md"
    if big_book.exists():
        print(f"\n{'='*50}")
        print(f"📚 Processing: 金融笔记知识库-完整版.md (big book)")

        sections = split_book(big_book)
        print(f"  📚 Split into {len(sections)} sections")

        for i, (sec_title, sec_content) in enumerate(sections):
            card_id = f"金融笔记知识库-完整版.md::{sec_title}"
            if card_id in existing_cards:
                print(f"  ⏭️  [{i+1}/{len(sections)}] {sec_title}")
                continue

            print(f"\n  [{i+1}/{len(sections)}] {sec_title} ({len(sec_content)} chars)")

            # Truncate if too long
            content = sec_content[:8000] if len(sec_content) > 8000 else sec_content
            if len(sec_content) > 8000:
                print(f"     ⚠️  Truncated {len(sec_content)} -> 8000 chars")

            card = extract_card(big_book, sec_title, content)
            if card:
                all_cards.append(card)
                json.dump(all_cards, open(cards_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                print(f"  🏷️  {card.get('primary_category','?')} | {card.get('one_sentence','')[:50]}")
            else:
                failed.append({"file": "金融笔记知识库-完整版.md", "section": sec_title})
                print("  ❌ Failed")

    # === Generate index maps ===
    print(f"\n{'='*50}")
    print("📊 Generating index maps...")

    category_map, tag_map, action_map = {}, {}, {}
    for card in all_cards:
        for cat in card.get("categories", []):
            category_map.setdefault(cat, []).append(card.get("title", card["id"]))
        for tag in card.get("tags", []):
            tag_map.setdefault(tag, []).append(card.get("title", card["id"]))
        action = card.get("action_bias", "education")
        action_map.setdefault(action, []).append(card.get("title", card["id"]))

    json.dump(category_map, open(INDEX_DIR / "category-map.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump(tag_map, open(INDEX_DIR / "tag-map.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump(action_map, open(INDEX_DIR / "action-map.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    with open(INDEX_DIR / "failed.jsonl", 'w') as f:
        for item in failed:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"\n{'='*50}")
    print(f"✅ Complete!")
    print(f"   cards.json: {len(all_cards)} cards")
    print(f"   category-map.json: {len(category_map)} categories")
    print(f"   tag-map.json: {len(tag_map)} tags")
    print(f"   action-map.json: {len(action_map)} actions")
    print(f"   failed.jsonl: {len(failed)} failures")


if __name__ == "__main__":
    main()
