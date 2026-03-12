/** Parse unknown value to finite number, default 0 */
export function toNumber(value: unknown): number {
  const parsed = Number(value)
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
