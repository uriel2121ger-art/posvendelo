/** Sanitize a value for safe inclusion in a CSV cell. */
export function toCsvCell(value: string): string {
  // eslint-disable-next-line no-control-regex -- strip control chars for CSV safety
  const clean = value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  const safe = /^[=+\-@\t\r\n]/.test(clean) ? `\t${clean}` : clean
  return `"${safe.replace(/"/g, '""')}"`
}

/** Create and trigger download of a CSV file with BOM for Excel compatibility. */
export function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const csv = [headers.map(toCsvCell).join(','), ...rows.map((r) => r.map(toCsvCell).join(','))].join('\n')
  const blob = new Blob([`\uFEFF${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

/** Parse a single CSV line respecting quoted fields (fields may contain commas). */
export function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i++
        continue
      }
      inQuotes = !inQuotes
      continue
    }
    if (!inQuotes && c === ',') {
      result.push(current.trim())
      current = ''
      continue
    }
    current += c
  }
  result.push(current.trim())
  return result
}

/** Return an ISO date string (YYYY-MM-DD) for N days ago. */
export function getIsoDateDaysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}
