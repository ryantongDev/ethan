#!/usr/bin/env python3
"""中医书籍章节切分脚本 v3 - 最终版"""
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
    safe = re.sub(r'[\\/:*?"<>|]', '_', chapter)
    fname = f"{safe}.md"
    path = os.path.join(book_dir, fname)
    meta = METADATA_TPL.format(
        book=book, src=BOOKS[book], level=level, chapter=chapter, auto=auto
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(meta + content)
    print(f"  [保存] {fname} ({len(content)}字)")

def split_by_size(content, book, chapter_prefix, level, target=1000, min_size=600):
    """按字符数切分，优先在条文编号处断开"""
    article_pat = re.compile(r'^([0-9０-９]+)．', re.MULTILINE)
    chunks = []
    start = 0
    chars = len(content)
    
    while start < chars:
        end = min(start + target, chars)
        search = content[start:end]
        matches = list(article_pat.finditer(search))
        
        if len(matches) > 1:
            cut = start + matches[1].start()
        elif matches:
            rest = content[end:]
            m2 = article_pat.search(rest)
            cut = end + m2.start() if m2 else min(start + target, chars)
        else:
            cut = min(start + target, chars)
        
        chunk = content[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = cut
    
    merged = []
    for c in chunks:
        if merged and len(merged[-1]) < min_size:
            merged[-1] += "\n\n" + c
        else:
            merged.append(c)
    
    for i, c in enumerate(merged, 1):
        ch_name = f"{chapter_prefix}第{i}节"
        save_chunk(book, ch_name, c, level)

def split_by_pattern(book, pattern_str, level, chunk_target=1000):
    """通用按正则切分"""
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    pat = re.compile(pattern_str, re.MULTILINE)
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if pat.match(part):
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", level, target=chunk_target)
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", level, target=chunk_target)

def split_by_pianming(book, level, chunk_target=1000):
    """按<篇名>切分，适用于脾胃论、内外伤辨、温病条辨、血证论"""
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    text = re.sub(r'^书名：[^\n]+\n', '', text)
    text = re.sub(r'^作者：[^\n]+\n', '', text)
    text = re.sub(r'^朝代：[^\n]+\n', '', text)
    text = re.sub(r'^年份：[^\n]+\n', '', text)
    
    pat = re.compile(r'<篇名>([^\n<]+)', re.IGNORECASE)
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", level, target=chunk_target)
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", level, target=chunk_target)

# ============================================================
# 伤寒论：按篇名分章，每章按条文切分
# ============================================================
def split_shanghan(book="伤寒论"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    pat = re.compile(r'<篇名>([^\n<]+)', re.IGNORECASE)
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "条文切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "条文切分")

# ============================================================
# 金匮要略：按卷/章结构
# ============================================================
def split_jinkui(book="金匮要略"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
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
# 伤寒论释义-胡希恕：
#   - 前言（目录+书摘+序等）-> 未分类_前言
#   - 第一部分（太阳病）-> 含第2/3/4章，合并为第一部分
#   - 第二～六部分 -> 各部分独立
#   - 最后5章（书摘）
# ============================================================
def split_huxishuo(book="伤寒论释义-胡希恕"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 找各部分的标题
    pat = re.compile(r'^第([一二三四五六七八九十百零0-9０-９]+)部分', re.MULTILINE)
    
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            # 是部分编号
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "部分切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "部分切分")

# ============================================================
# 桂林古本伤寒杂病论：按"伤寒杂病论卷第X"切分
# ============================================================
def split_guilin(book="桂林古本伤寒杂病论"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    pat = re.compile(r'(伤寒杂病论卷[第上下]+[一二三四五六七八九十百零0-9０-９0-9]+)', re.UNICODE)
    
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if pat.match(part):
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "卷切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "卷切分")

# ============================================================
# 黄帝内经：
# 文本包含长篇导读（介绍书名、成书年代等），之后是81篇素问+灵枢
# 用"篇名"关键词切分
# ============================================================
def split_huangdi(book="黄帝内经"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 先去掉序言类内容（名著通览部分）
    # 找"篇名"或第X篇模式
    pat = re.compile(r'^《?(素问|灵枢)[》]?\s*[：:·]*\s*第?([一二三四五六七八九十百零0-9０-９]+)[篇章]?', re.MULTILINE)
    
    parts = pat.split(text)
    
    if len(parts) <= 2:
        # 尝试按"篇名"或"第X篇"
        pat2 = re.compile(r'^(素问|灵枢|阴阳应象大论|六节藏象论|五脏生成论|五脏别论|经脉别论|脏气法时论|至真要大论|天年论)[篇]?', re.MULTILINE)
        parts = pat2.split(text)
    
    if len(parts) <= 2:
        # 直接按800字切分，不分类
        split_by_pattern(book, r'^(?=.)', "章节切分", chunk_target=800)
        return
    
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")

# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    dispatch = {
        "伤寒论": split_shanghan,
        "金匮要略": split_jinkui,
        "伤寒论释义-胡希恕": split_huxishuo,
        "胡希恕经方理论与实践": lambda: split_by_pattern("胡希恕经方理论与实践", r'^第[一二三四五六七八九十百零0-9０-９]+章', "章节切分"),
        "桂林古本伤寒杂病论": split_guilin,
        "脾胃论": lambda: split_by_pianming("脾胃论", "篇名切分"),
        "内外伤辨": lambda: split_by_pianming("内外伤辨", "篇名切分"),
        "黄帝内经": split_huangdi,
        "温病条辨": lambda: split_by_pianming("温病条辨", "篇名切分"),
        "景岳全书": lambda: split_by_pianming("景岳全书", "篇名切分"),
        "血证论": lambda: split_by_pianming("血证论", "篇名切分"),
    }
    
    for book in BOOKS:
        print(f"\n{'='*50}\n处理: {book}")
        try:
            dispatch[book]()
            print(f"完成: {book}")
        except Exception as e:
            print(f"错误 ({book}): {e}")
            import traceback; traceback.print_exc()