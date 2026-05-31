#!/usr/bin/env python3
"""中医书籍章节切分脚本 v4 - 最终修复版"""
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

def split_by_pattern(book, pattern_str, level, chunk_target=1000, extra_sep=''):
    """通用按正则切分"""
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    if extra_sep:
        text = text.replace(extra_sep, '\n')
    
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
# 伤寒论释义-胡希恕：按第X部分切分
# ============================================================
def split_huxishuo(book="伤寒论释义-胡希恕"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    pat = re.compile(r'^第([一二三四五六七八九十百零0-9０-９]+)部分', re.MULTILINE)
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "部分切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "部分切分")

# ============================================================
# 胡希恕经方理论与实践：按"第X章"切分
# ============================================================
def split_huxishuo_jingfang(book="胡希恕经方理论与实践"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 直接找"第X章"标题 - 它们独占一行，前面有换行
    # The pattern is like: \n第一章桂枝汤类方\n
    pat = re.compile(r'\n第([一二三四五六七八九十百零0-9０-９]+)章([^\n]+?)\n')
    parts = pat.split(text)
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 3 == 1:
            # 这是"第X章"中的数字部分
            current_chapter = "第" + part + "章"
            current_content = ""
        elif i % 3 == 2:
            # 这是章名（方剂类别名）
            current_chapter += part.strip()
            current_content = ""
        else:
            # 这是章节内容
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "章节切分")

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
# 黄帝内经：按篇名切分（素问81篇+灵枢81篇）
# 篇名出现在独立行，如"上古天真论篇"、"四气调神大论篇"
# ============================================================
def split_huangdi(book="黄帝内经"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 先找《素问》部分，从那里开始按篇名切分
    suwen_start = text.find('《素问》')
    if suwen_start == -1:
        suwen_start = 0
    
    # 篇名格式：XXXX论篇 或 XXXX大论篇
    pat = re.compile(r'^([A-Za-z\u4e00-\u9fff]{2,15}大?论篇)\s*$', re.MULTILINE)
    
    # 在素问开始位置之后进行匹配
    suwen_text = text[suwen_start:]
    parts = pat.split(suwen_text)
    
    current_chapter = "未分类"
    current_content = ""
    
    for i, part in enumerate(parts):
        if i == 0:
            current_content = part
            continue
        if i % 2 == 1:
            # 篇名
            if current_content.strip():
                split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "篇切分")

# ============================================================
# 景岳全书：按篇名切分
# ============================================================
def split_jingyue(book="景岳全书"):
    fname = os.path.join(SRC, BOOKS[book])
    with open(fname, encoding="utf-8") as f:
        text = f.read()
    
    # 景岳全书有篇名标记
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
                split_by_size(current_content.strip(), book, current_chapter + "_", "篇名切分", target=800)
            current_chapter = part.strip()
            current_content = ""
        else:
            current_content = part
    
    if current_content.strip():
        split_by_size(current_content.strip(), book, current_chapter + "_", "篇名切分", target=800)

# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    dispatch = {
        "伤寒论": split_shanghan,
        "金匮要略": split_jinkui,
        "伤寒论释义-胡希恕": split_huxishuo,
        "胡希恕经方理论与实践": split_huxishuo_jingfang,
        "桂林古本伤寒杂病论": split_guilin,
        "脾胃论": lambda: split_by_pianming("脾胃论", "篇名切分"),
        "内外伤辨": lambda: split_by_pianming("内外伤辨", "篇名切分"),
        "黄帝内经": split_huangdi,
        "温病条辨": lambda: split_by_pianming("温病条辨", "篇名切分"),
        "景岳全书": split_jingyue,
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