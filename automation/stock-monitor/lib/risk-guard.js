/**
 * risk-guard.js
 * 纪律执行强化层：如果回复涉及买卖但没有区间，自动追加纪律提醒。
 * 同时替换软词为坚定表达，防止 Agent 语气变软。
 */

const SOFT_WORDS_MAP = {
  '可以考虑': '按纪律执行',
  '或许': '纪律上',
  '可能': '当前看',
  '看情况': '看触发条件',
  '再观察一下': '只观察一个触发价，不拖延',
  '等等看': '不要无条件等',
  '等一下': '不要等',
  '再等等': '不要再等',
  '等反弹': '不幻想反弹，执行纪律',
  '可以再拿': '执行纪律，不贪',
};

const SELL_TRIGGER_PATTERNS = [
  /买入|买点|卖出|卖点|止损|止盈|减仓|清仓|仓位|还能拿|要不要卖|要不要买|拿着|持仓|加仓|建仓|追高|抄底|换股/,
];

const RANGE_PATTERNS = [
  /区间|附近|%|止损价|止盈价|执行价|卖出价|买入价|价格范围|目标价|买入价|卖出价|挂单|低于|高于|突破|回踩/,
];

/**
 * 判断文本是否包含交易意图
 */
function hasTradeIntent(text) {
  return SELL_TRIGGER_PATTERNS.some(p => p.test(text));
}

/**
 * 判断文本是否包含价格区间
 */
function hasRange(text) {
  return RANGE_PATTERNS.some(p => p.test(text));
}

/**
 * 替换软词为坚定表达
 */
function replaceSoftWords(text) {
  let result = text;
  for (const [soft, firm] of Object.entries(SOFT_WORDS_MAP)) {
    result = result.split(soft).join(firm);
  }
  return result;
}

/**
 * 强制追加纪律提醒（如果缺少区间）
 */
function appendDisciplineNote(text) {
  return text + `

【执行纪律补充】
这类信号不能只看方向，必须带价格区间执行。卖出时不追求最高点，能卖在计划区间内就是合格交易；买入时只在触发条件成立后小仓试错，错了立刻走。`;
}

/**
 * 主函数：对最终回复文本进行纪律强化
 * @param {string} text - 原始回复文本
 * @param {object} context - 可选上下文 { userProfile: 'sell_hesitation' }
 * @returns {string} - 强化后的回复文本
 */
export function enforceExecutionDiscipline(text, context = {}) {
  const original = String(text || '');

  if (!hasTradeIntent(original)) {
    return original;
  }

  let patched = replaceSoftWords(original);

  if (!hasRange(patched)) {
    patched = appendDisciplineNote(patched);
  }

  return patched;
}

/**
 * 快捷包装器：用于替换已有的 applyRiskGuard 调用
 * @param {string} text
 * @returns {string}
 */
export function applyRiskGuard(text) {
  return enforceExecutionDiscipline(text);
}

export default { enforceExecutionDiscipline, applyRiskGuard };