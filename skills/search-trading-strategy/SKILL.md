---
name: search-trading-strategy
description: 短线交易战法检索器。这是老张的专属"战法笔记"。当用户询问以下任何问题时，必须调用此工具：
- "这个形态该怎么操作？"
- "断板反包能抄底吗？"
- "今天竞价爆量怎么看？"
- "尾盘拉升要不要追？"
- 任何涉及个股异动、K线形态、量价配合、买卖点评估的需求。

返回匹配战法的名称、核心逻辑、买卖条件。无匹配时返回兜底提示。
---

# 短线交易战法检索工具

## Tool ID
`search_trading_strategy`

## Parameters Schema
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "用户描述的行情形态或问题，如'断板低开爆量'"
    },
    "category": {
      "type": "string",
      "enum": ["买入", "卖出", "形态", "量价", "竞价", "尾盘", "综合"],
      "description": "可选，战法分类筛选"
    }
  },
  "required": ["query"]
}
```

## 代码实现

### 代码文件：references/search_index.py

```python
import json
import os
import fnmatch

KB_DIR = "/root/ryantongDev/md/金融炒股/trading_kb"
INDEX_PATH = os.path.join(KB_DIR, "strategy_index.json")

def main(query: str, category: str = None):
    """
    短线交易战法检索器
    查询用户描述的形态/问题，从361条战法索引中匹配最相关的Top3。
    匹配逻辑：
    1. 战法名精确命中（+2分）
    2. 关键词命中（每命中一个+1分）
    3. 优先返回最高分的前3条
    4. 无匹配 → 兜底提示："没查到对应战法，老张建议空仓看戏。"
    """
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

    results = []
    query_lower = query.lower()

    for item in index:
        strategy_name = item.get("strategy_name", "")
        keywords = item.get("keywords", [])

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

    # 读取详细内容（读取markdown文件内容，提取买卖条件）
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
                # 从 markdown 内容中提取关键字段
                for line in content.split('\n'):
                    if '核心交易逻辑' in line:
                        core_logic = line.split('核心交易逻辑')[1].strip('：:：')[1:].strip()
                    elif '买入/切入点' in line or '买点' in line:
                        buy_cond = line.split('买点')[0].split('：')[1].strip() if '：' in line else line.split('买点')[1].strip()
                    elif '卖出/止损点' in line or '止损' in line:
                        sell_cond = line.split('止损')[0].split('：')[1].strip() if '：' in line else line.split('止损')[1].strip()
            except:
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
        "strategies": strategies_detail
    }
```