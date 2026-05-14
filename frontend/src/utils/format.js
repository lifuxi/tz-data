/**
 * Format number with thousand separators.
 * @param {number|string} value
 * @param {number} [decimals] - Optional decimal places
 * @returns {string}
 */
export function formatNumber(value, decimals = 0) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return num.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/**
 * Format money with thousand separators and 万/亿 abbreviation.
 */
export function formatMoney(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  const abs = Math.abs(num)
  if (abs >= 1e8) return (num / 1e8).toFixed(2).replace(/\.?0+$/, '') + ' 亿'
  if (abs >= 1e4) return (num / 1e4).toFixed(2).replace(/\.?0+$/, '') + ' 万'
  return num.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

/**
 * Format money with full thousand separators (no abbreviation).
 */
export function formatMoneyFull(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/**
 * Format PnL with sign and thousand separators.
 */
export function formatPnl(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  const sign = num > 0 ? '+' : ''
  return sign + formatMoney(num)
}
