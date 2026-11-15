import axios from 'axios'

export const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    let message = error.message || '请求失败'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      message = detail.map((item) => item.msg || JSON.stringify(item)).join('；')
    } else if (detail) {
      message = JSON.stringify(detail)
    }
    if (error.code === 'ECONNABORTED') {
      message = '请求超时，请检查数据库连接或缩小查询范围'
    }
    const wrapped = new Error(message)
    wrapped.status = error.response?.status
    return Promise.reject(wrapped)
  },
)

function cleanParams(params = {}) {
  const output = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') output[key] = value
  }
  return output
}

export const api = {
  health: () => http.get('/health'),

  listConnections: () => http.get('/connections'),
  getConnection: (id) => http.get(`/connections/${id}`),
  createConnection: (payload) => http.post('/connections', payload),
  updateConnection: (id, payload) => http.put(`/connections/${id}`, payload),
  deleteConnection: (id) => http.delete(`/connections/${id}`),
  testConnection: (payload) => http.post('/connections/test', payload),

  catalogs: (id, database) =>
    http.get(`/connections/${id}/catalogs`, { params: cleanParams({ database }) }),
  tables: (id, database, schema) =>
    http.get(`/connections/${id}/tables`, { params: cleanParams({ database, schema }) }),
  tableDetail: (id, table, database, schema) =>
    http.get(`/connections/${id}/tables/${encodeURIComponent(table)}`, {
      params: cleanParams({ database, schema }),
    }),
  rows: (id, table, params = {}) =>
    http.get(`/connections/${id}/tables/${encodeURIComponent(table)}/rows`, {
      params: cleanParams(params),
    }),
  insertRow: (id, table, values, database, schema) =>
    http.post(`/connections/${id}/tables/${encodeURIComponent(table)}/rows`, { values }, {
      params: cleanParams({ database, schema }),
    }),
  updateRow: (id, table, pk, values, database, schema) =>
    http.put(`/connections/${id}/tables/${encodeURIComponent(table)}/rows`, { pk, values }, {
      params: cleanParams({ database, schema }),
    }),
  deleteRow: (id, table, pk, database, schema) =>
    http.delete(`/connections/${id}/tables/${encodeURIComponent(table)}/rows`, {
      data: { pk, values: {} },
      params: cleanParams({ database, schema }),
    }),
  completion: (id, database, schema) =>
    http.get(`/connections/${id}/completion`, { params: cleanParams({ database, schema }) }),
  overview: (id, database, schema) =>
    http.get(`/connections/${id}/overview`, { params: cleanParams({ database, schema }) }),

  query: (id, payload) => http.post(`/connections/${id}/query`, payload),

  tableExportUrl: (id, table, params = {}) => {
    const search = new URLSearchParams(cleanParams(params)).toString()
    return `/api/connections/${id}/tables/${encodeURIComponent(table)}/export${search ? `?${search}` : ''}`
  },
}
