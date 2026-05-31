import json
import os

KB_DIR = "/root/ryantongDev/md/金融炒股/trading_kb"
INDEX_PATH = os.path.join(KB_DIR, "strategy_index.json")
CATEGORY_PATH = os.path.join(KB_DIR, "category_index.json")


def main(query: str, category: str = None):
    """
    短线交易战法检索器（分类增强版）
    
    参数:
        query: 用户描述的行情形态或问题，如'断板低开爆量'
        category: 可选，按分类筛选 ['买入','卖出','形态','量价','竞价','尾盘','综合']
    
    匹配逻辑：
    1. 优先在指定分类内搜索（如指定category）
    2. 战法名精确命中（+2分）
    3. 关键词命中（每命中一个+1分）
    4. 返回最高分的前3条
    5. 无匹配 → 兜底提示："没查到对应战法，老张建议空仓看戏。"
    """
    # 加载主索引
    if not os.path.exists(INDEX_PATH):
        return {
            "matched": False,
            "message": "系统异常：老张的笔记(索引文件)丢失，请检查路径。",
            "strategies": []
        }

    try:
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            index = json.load(f)
    except Exception as e:
        return {
            "matched": False,
            "message": f"笔记解析失败: {e}",
            "strategies": []
        }

    # 如果指定了分类，加载分类索引做预筛选
    cat_filter = None
    if category and os.path.exists(CATEGORY_PATH):
        try:
            with open(CATEGORY_PATH, 'r', encoding='utf-8') as f:
                cat_data = json.load(f)
            # 映射用户类别名到分类索引key
            cat_map = {
                '买入': '买入/买点',
                '卖出': '卖出/止损',
                '形态': 'K线形态',
                '量价': '量价关系',
                '竞价': '竞价/集合竞价',
                '尾盘': '尾盘/收盘',
                '综合': '综合/其他'
            }
            cat_key = cat_map.get(category, category)
            if cat_key in cat_data and cat_data[cat_key]:
                cat_filter = set(cat_data[cat_key])
        except Exception:
            pass

    results = []
    query_lower = query.lower()

    for item in index:
        strategy_name = item.get("strategy_name", "")
        keywords = item.get("keywords", [])

        # 分类预筛选
        if cat_filter and strategy_name not in cat_filter:
            continue

        # 计算命中分数
        name_hit = strategy_name in query
        keyword_hits = sum(1 for kw in keywords if kw in query_lower or kw.lower() in query_lower)
        total_score = keyword_hits + (2 if name_hit else 0)

        if total_score == 0:
            continue

        results.append({
            "name": strategy_name,
            "score": total_score,
            "keywords": keywords,
            "file_path": item.get("file_path", "")
        })

    if not results:
        return {
            "matched": False,
            "message": "老张翻遍了笔记，暂无完全匹配的战法。建议：1) 尝试更通用的关键词；2) 基于量价关系通用原则进行分析，不要盲目动手。",
            "strategies": []
        }

    # 按分数降序，取Top3
    results.sort(key=lambda x: x["score"], reverse=True)
    top3 = results[:3]

    # 读取详细内容
    strategies_detail = []
    for r in top3:
        fp = r["file_path"]
        content = ""
        buy_cond = "【文本未提及】"
        sell_cond = "【文本未提及】"
        core_logic = "详见原文件"

        if os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                for line in content.split('\n'):
                    if '核心交易逻辑' in line and '：' in line:
                        core_logic = line.split('：', 1)[1].strip()
                    elif ('买入/切入点' in line or '买点' in line) and '：' in line:
                        buy_cond = line.split('：', 1)[1].strip()
                    elif ('卖出/止损点' in line or '止损' in line) and '：' in line:
                        sell_cond = line.split('：', 1)[1].strip()
            except Exception:
                pass

        strategies_detail.append({
            "name": r["name"],
            "score": r["score"],
            "core_logic": core_logic,
            "buy_condition": buy_cond,
            "sell_condition": sell_cond,
            "keywords": r["keywords"]
        })

    return {
        "matched": True,
        "count": len(strategies_detail),
        "category_filter": category,
        "strategies": strategies_detail
    }