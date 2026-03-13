/** Parse unknown value to finite number, default 0.
 *  Strips currency symbols ($), thousands separators (,), and whitespace
 *  so Excel-formatted values like "$1,500.50" parse correctly.
 */
export function toNumber(value: unknown): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  if (value == null) return 0
  const raw = String(value).trim()
  // Fast path: already a clean number
  const fast = Number(raw)
  if (Number.isFinite(fast)) return fast
  // Strip currency symbols, spaces, and thousands separators
  const cleaned = raw.replace(/[$\s,]/g, '')
  const parsed = Number(cleaned)
  return Number.isFinite(parsed) ? parsed : 0
}

/** Format number as currency string: $1,234.56
 * Uses integer-cent rounding to avoid IEEE 754 floating-point errors.
 * (1.005).toFixed(2) → "1.00" in V8; Math.round(1.005 * 100) → 101 → "1.01" ✓
 */
export function money(value: string | number): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (!Number.isFinite(num)) return '$0.00'
  const negative = num < 0
  const cents = Math.round(Math.abs(num) * 100)
  const pesos = Math.floor(cents / 100)
  const pesosStr = pesos.toLocaleString('es-MX')
  const centavos = (cents % 100).toString().padStart(2, '0')
  return `${negative ? '-' : ''}$${pesosStr}.${centavos}`
}
