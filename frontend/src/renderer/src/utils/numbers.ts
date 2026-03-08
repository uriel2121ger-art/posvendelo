/** Parse unknown value to finite number, default 0 */
export function toNumber(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

/** Format number as currency string: $1,234.56 */
export function money(value: number): string {
  return `$${value.toFixed(2)}`
}
