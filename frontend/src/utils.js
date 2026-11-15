export const DRIVERS = {
  sqlite: { label: 'SQLite', color: '#0ea5e9', short: 'SQ' },
  mysql: { label: 'MySQL', color: '#f59e0b', short: 'MY' },
  postgresql: { label: 'PostgreSQL', color: '#6366f1', short: 'PG' },
  mssql: { label: 'SQL Server', color: '#ef4444', short: 'MS' },
  oracle: { label: 'Oracle', color: '#dc2626', short: 'OR' },
}

export const DRIVER_OPTIONS = Object.entries(DRIVERS).map(([value, meta]) => ({
  value,
  label: meta.label,
}))

export const DEFAULT_PORTS = {
  mysql: 3306,
  postgresql: 5432,
  mssql: 1433,
  oracle: 1521,
}

export function kindMeta(kind) {
  return DRIVERS[kind] || { label: kind || '未知', color: '#64748b', short: 'DB' }
}

export function kindLabel(kind) {
  return kindMeta(kind).label
}

export function kindColor(kind) {
  return kindMeta(kind).color
}

export function connectionSubtitle(connection) {
  if (!connection) return ''
  if (connection.kind === 'sqlite') {
    const path = connection.sqlite_path || ''
    return path.split('/').pop() || path || '未选择文件'
  }
  const host = connection.host || '127.0.0.1'
  const port = connection.port ? `:${connection.port}` : ''
  const database = connection.database ? `/${connection.database}` : ''
  return `${host}${port}${database}`
}

export function formatNumber(value, fallback = '—') {
  if (value === null || value === undefined) return fallback
  return Number(value).toLocaleString('zh-CN')
}

export function formatBytes(bytes, fallback = '—') {
  if (bytes === null || bytes === undefined) return fallback
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = Number(bytes)
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`
}

export function shortType(type = '') {
  if (!type) return ''
  return type
    .replace(/\([^)]*\)/g, '')
    .replace(/character varying/i, 'varchar')
    .replace(/timestamp without time zone/i, 'timestamp')
    .replace(/timestamp with time zone/i, 'timestamptz')
    .trim()
    .toLowerCase()
}

export function columnWidth(column) {
  const name = (column.name || '').length
  const type = (column.type || '').length
  return Math.min(360, Math.max(120, (name + Math.min(type, 14)) * 9 + 40))
}

export function displayCell(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function normalizeDbValue(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'boolean' || typeof value === 'number') return value
  if (typeof value === 'object') return JSON.stringify(value)
  return value
}

export function downloadCsv(filename, columns, rows) {
  const escape = (value) => {
    if (value === null || value === undefined) return ''
    const text = typeof value === 'object' ? JSON.stringify(value) : String(value)
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const lines = [columns.map((column) => escape(column.name)).join(',')]
  for (const row of rows) {
    lines.push(row.map((value) => escape(value)).join(','))
  }
  const blob = new Blob([`\ufeff${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}
