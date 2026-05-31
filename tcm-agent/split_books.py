#!/usr/bin/env python3
"""中医书籍章节切分脚本"""
import re, os

SRC = "/root/.openclaw/workspace/tcm-agent/knowledge/01_原书全文"
DST = "/root/.openclaw/workspace/tcm-agent/knowledge/02_章节切分"

BOOKS = {
    "伤寒论": "伤寒论.txt",
    "金匮要略": "金匮要略.txt",
    "伤寒论释义-胡希恕": "伤寒论释义-胡希恕.txt",
    "胡希恕经方理论与实践": "胡希恕经方理论与实践.txt",
    "桂林古本伤寒杂病论": "桂林古本伤寒杂病论.txt",
    "脾胃论": "脾胃论.txt",
    "内外伤辨": "内外伤辨.txt",
    "黄帝内经": "黄帝内经.txt",
    "温病条辨": "温病条辨.txt",
    "景岳全书": "景岳全书.txt",
    "血证论": "血证论.txt",
}

METADATA_TPL = """---
书名: {book}
来源文件: {src}
切分层级: {level}
章节: {chapter}
是否自动切分: {auto}
---

"""

def save_chunk(book, chapter, content, level, auto="是"):
    book_dir = os.path.join(DST, book)
    # sanitize chapter name for filename
    safe = re.sub(r'[\\/:*?"<>|]', '_', chapter)
    fname = f"{safe}.md"
    path = os.path.join(book_dir, fname)
    meta = METADATA_TPL.format(
        book=book, src=BOOKS[book], level=level, chapter=chapter, auto=auto
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(meta + content)
    print(f"  [保存] {path} ({len(content)}字)")

def split_by_size(content, book, chapter_prefix, level, target=1000, min_size=600):
    """按字符数切分，优先在条文编号处断开"""
    # 伤寒论条文编号：数字＋・ 或 数字+.
    article_pat = re.compile(r'^([0-9０-９]+)．', re.MULTILINE)
    
    chunks = []
    start = 0
    chars = len(content)
    
    while start < chars:
        end = min(start + target, chars)
        
        # 尝试找最近的文章编号作为断点
        search = content[start:end]
        matches = list(article_pat.finditer(search))
        
        if len(matches) > 1:
            # 在第二个条文之前断开（保留第一个条文完整）
            cut = start + matches[1].start()
        elif matches:
            # 只有一个，找下一个
            rest = content[end:]
            m2 = article_pat.search(rest)
            if m2:
                cut = end + m2.start()
            else:
                cut = min(start + target, chars)
        else:
            cut = min(start + target, chars)
        
        chunk = content[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = cut
    
    # 合并太小的 chunk
    merged = []
    for c in chunks:
        if merged and len(merged[-1]) < min_size:
            merged[-1] += "\n\n" + c
        else:
            merged.append(c)
    
    for i, c in enumerate(merged, 1):
        ch_name = f"{chapter_prefix}第{i}节"
        save_chunk(book, ch_name, c, level)

# ============================================================
# 伤寒论切分（按篇名分章，每章按条文切分）
# ============================================================
def split_shanghan(book="伤寒论"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 提取各篇
    # 格式：<篇名>辨太阳病脉证并治上
    pat = re.compile(r'<篇名>([^\n<]+)', re.IGNORECASE)
    parts = pat.split(text)
    # parts[0]是开头，parts[1]是第一章名，parts[2]是内容，...
    
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            # 是篇名，保存之前的
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "条文切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "条文切分")

# ============================================================
# 金匮要略切分（按卷/章结构）
# ============================================================
def split_jinkui(book="金匮要略"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 按 "第X卷 第X章" 分割
    pat = re.compile(r'(第[一二三四五六七八九十百零0-9０-９]+卷\s+第[一二三四五六七八九十百零0-9０-９]+章)', re.UNICODE)
    
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if pat.match(part):
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "章节切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "章节切分")

# ============================================================
# 黄帝内经切分（素问/灵枢 各81篇）
# ============================================================
def split_huangdi(book="黄帝内经"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 找篇名模式：卷/篇名
    pat = re.compile(r'^第[一二三四五六七八九十百零0-9０-９]+篇', re.MULTILINE)
    
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if pat.match(part):
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")

# ============================================================
# 通用切分（伤寒论释义、脾胃论等）
# ============================================================
def split_generic(book, chunk_target=1000):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 尝试找章节标记（中文数字标题）
    pat = re.compile(r'^第[一二三四五六七八九十百零0-9０-９]+[章节部篇]', re.MULTILINE)
    
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if pat.match(part):
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "章节切分", target=chunk_target)
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "章节切分", target=chunk_target)

# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    for book in BOOKS:
        print(f"\n{'='*50}\n处理: {book}")
        try:
            if book == "伤寒论":
                split_shanghan(book)
            elif book == "金匮要略":
                split_jinkui(book)
            elif book == "黄帝内经":
                split_huangdi(book)
            else:
                split_generic(book)
            print(f"完成: {book}")
        except Exception as e:
            print(f"错误 ({book}): {e}")
            import traceback; traceback.print_exc()