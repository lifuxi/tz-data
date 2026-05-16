import axios from 'axios'
import { ElMessage } from 'element-plus'

// Create axios instance
const apiClient = axios.create({
  baseURL: '/api/maintenance',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if needed
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// API methods
export const catalogAPI = {
  // List catalogs
  list(params = {}) {
    return apiClient.get('/catalogs', { params })
  },
  
  // Get catalog by ID
  get(id) {
    return apiClient.get(`/catalogs/${id}`)
  },
  
  // Create catalog
  create(data) {
    return apiClient.post('/catalogs', data)
  },
  
  // Update catalog
  update(id, data) {
    return apiClient.put(`/catalogs/${id}`, data)
  },
  
  // Delete catalog
  delete(id) {
    return apiClient.delete(`/catalogs/${id}`)
  },
}

export const healthAPI = {
  // Generate health snapshot
  generate() {
    return apiClient.post('/health-snapshots/generate')
  },
  
  // List health snapshots
  list(params = {}) {
    return apiClient.get('/health-snapshots', { params })
  },
  
  // Get latest snapshot
  getLatest() {
    return apiClient.get('/health-snapshots/latest')
  },
}

export const accountAPI = {
  // List accounts
  list() {
    return apiClient.get('/accounts')
  },
  
  // Create account
  create(data) {
    return apiClient.post('/accounts', data)
  },
  
  // Update account
  update(id, data) {
    return apiClient.put(`/accounts/${id}`, data)
  },
  
  // Delete account
  delete(id) {
    return apiClient.delete(`/accounts/${id}`)
  },
}

export const statementAPI = {
  // Upload statement file
  upload(formData) {
    return apiClient.post('/statements/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
  
  // List statements
  list(params = {}) {
    return apiClient.get('/statements', { params })
  },
  
  // Parse statement
  parse(statementId) {
    return apiClient.post(`/statements/${statementId}/parse`)
  },
}

export const alertAPI = {
  // List alerts
  list(params = {}) {
    return apiClient.get('/alerts', { params })
  },

  // Get recent alerts
  getRecent(limit = 50) {
    return apiClient.get('/alerts/recent', { params: { limit } })
  },
}

export const exchangeAPI = {
  list() {
    return apiClient.get('/exchanges')
  },
  get(id) {
    return apiClient.get(`/exchanges/${id}`)
  },
  create(data) {
    return apiClient.post('/exchanges', data)
  },
  update(id, data) {
    return apiClient.put(`/exchanges/${id}`, data)
  },
  delete(id) {
    return apiClient.delete(`/exchanges/${id}`)
  },
}

export const productAPI = {
  list(params = {}) {
    return apiClient.get('/products', { params })
  },
  get(id) {
    return apiClient.get(`/products/${id}`)
  },
  create(data) {
    return apiClient.post('/products', data)
  },
  update(id, data) {
    return apiClient.put(`/products/${id}`, data)
  },
  delete(id) {
    return apiClient.delete(`/products/${id}`)
  },
}

export const contractAPI = {
  list(params = {}) {
    return apiClient.get('/contracts', { params })
  },
  get(id) {
    return apiClient.get(`/contracts/${id}`)
  },
  create(data) {
    return apiClient.post('/contracts', data)
  },
  update(id, data) {
    return apiClient.put(`/contracts/${id}`, data)
  },
  delete(id) {
    return apiClient.delete(`/contracts/${id}`)
  },
  // Sync from Tushare
  syncFromTushare(exchange = 'CFFEX', contractType = 'futures') {
    return apiClient.post('/contracts/import-from-tushare', null, { params: { exchange, contract_type: contractType } })
  },
  checkExpired(referenceDate = null) {
    return apiClient.post('/contracts/check-expired', null, { params: { reference_date: referenceDate } })
  },
  getExpiring(date = null, daysAhead = 30) {
    return apiClient.get('/contracts/expiring', { params: { date, days_ahead: daysAhead } })
  },
}

export const tradeCalendarAPI = {
  init(yearStart = 2025, yearEnd = 2026) {
    return apiClient.post('/trade-calendar/init', null, { params: { year_start: yearStart, year_end: yearEnd } })
  },
  getTradingDays(startDate, endDate, exchangeCode = 'ALL') {
    return apiClient.get('/trade-calendar/trading-days', { params: { start_date: startDate, end_date: endDate, exchange_code: exchangeCode } })
  },
  isTradingDay(tradeDate, exchangeCode = 'ALL') {
    return apiClient.get('/trade-calendar/is-trading-day', { params: { trade_date: tradeDate, exchange_code: exchangeCode } })
  },
  addHoliday(tradeDate, holidayName, exchangeCode = 'ALL') {
    return apiClient.post('/trade-calendar/add-holiday', null, { params: { trade_date: tradeDate, holiday_name: holidayName, exchange_code: exchangeCode } })
  },
}

export const mainContractAPI = {
  get(productCode, date) {
    return apiClient.get(`/main-contract/${productCode}`, { params: { date } })
  },
  set(productCode, date, contractCode) {
    return apiClient.post(`/main-contract/${productCode}`, null, { params: { date, contract_code: contractCode } })
  },
  series(productCode, startDate, endDate) {
    return apiClient.get(`/main-contract/${productCode}/series`, { params: { start_date: startDate, end_date: endDate } })
  },
  rollovers(productCode, startDate, endDate) {
    return apiClient.get(`/main-contract/${productCode}/rollovers`, { params: { start_date: startDate, end_date: endDate } })
  },
  autoPopulate(productCode, startDate, endDate) {
    return apiClient.post(`/main-contract/${productCode}/auto-populate`, null, { params: { start_date: startDate, end_date: endDate } })
  },
}

export const syncAPI = {
  // Get sync status
  getStatus() {
    return apiClient.get('/sync/status')
  },

  // Trigger sync for a catalog
  trigger(catalogId, mode = 'incremental', startDate = null, endDate = null) {
    return apiClient.post('/sync/trigger', null, {
      params: { catalog_id: catalogId, mode, start_date: startDate, end_date: endDate }
    })
  },

  // Get sync history
  history(params = {}) {
    return apiClient.get('/sync/history', { params })
  },
}

export const specialDateAPI = {
  list(params = {}) {
    return apiClient.get('/trade-calendar/special-dates', { params })
  },
  create(data) {
    return apiClient.post('/trade-calendar/special-dates', null, { params: data })
  },
  delete(exchangeCode, tradeDate) {
    return apiClient.delete('/trade-calendar/special-dates', { params: { exchange_code: exchangeCode, trade_date: tradeDate } })
  },
}

export const tradingHoursAPI = {
  list() {
    // No list endpoint, fetch individual templates
    return Promise.resolve({ data: [] })
  },
  get(templateId) {
    return apiClient.get(`/trading-hours/${templateId}`)
  },
  getSessions(templateId) {
    return apiClient.get(`/trading-hours/${templateId}/sessions`)
  },
  isTradingTime(templateId, timeStr) {
    return apiClient.get('/trading-hours/is-trading-time', { params: { template_id: templateId, time_str: timeStr } })
  },
  create(data) {
    return apiClient.post('/trading-hours/templates', null, { params: data })
  },
}

export const statementVerifyAPI = {
  verifyBalance(data) {
    return apiClient.post('/statements/verify-balance', data)
  },
  reconcile(trades, marketQuotes, tolerance = 5.0) {
    return apiClient.post('/statements/reconcile', { trades, market_quotes: marketQuotes, price_tolerance_pct: tolerance })
  },
  reconcileFromDb(accountId, startDate, endDate, tolerance = 5.0) {
    return apiClient.get(`/statements/reconcile/${accountId}`, { params: { start_date: startDate, end_date: endDate, price_tolerance_pct: tolerance } })
  },
}

export const dashboardAPI = {
  get() {
    return apiClient.get('/dashboard')
  },
}

export default apiClient
