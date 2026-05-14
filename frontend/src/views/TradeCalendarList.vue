<template>
  <div class="page-container">
    <!-- ===== Tab 1: 交易所日历 ===== -->
    <el-tabs v-model="activeTab" type="card">
      <el-tab-pane label="交易所日历" name="exchange">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>交易所日历</span>
              <div>
                <el-button type="primary" @click="systemInit" :loading="initLoading">
                  <el-icon><Refresh /></el-icon>
                  系统初始化
                </el-button>
                <el-button type="success" @click="holidayDialogVisible = true">
                  <el-icon><Plus /></el-icon>
                  节假日
                </el-button>
                <el-button @click="checkStatus">刷新状态</el-button>
              </div>
            </div>
          </template>

          <!-- 系统状态 -->
          <el-descriptions :column="4" border class="status-desc">
            <el-descriptions-item label="年份范围">{{ statusData.yearRange || '-' }}</el-descriptions-item>
            <el-descriptions-item label="交易所记录">{{ statusData.exchangeRecords || 0 }}</el-descriptions-item>
            <el-descriptions-item label="产品日历数">{{ statusData.productCount || 0 }}</el-descriptions-item>
            <el-descriptions-item label="总记录数">{{ statusData.totalRecords || 0 }}</el-descriptions-item>
          </el-descriptions>

          <!-- 产品日历概览 -->
          <el-divider content-position="left">CFFEX 产品日历概览</el-divider>
          <el-table :data="productOverview" stripe v-loading="loading" style="margin-top:16px">
            <el-table-column prop="product_code" label="商品代码" width="100" />
            <el-table-column prop="product_type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag :type="row.product_type === '期货' ? '' : 'warning'" size="small">{{ row.product_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="listing_date" label="上市日期" width="120" sortable />
            <el-table-column prop="date_range" label="数据范围" width="200">
              <template #default="{ row }">{{ row.dateRange || '未初始化' }}</template>
            </el-table-column>
            <el-table-column prop="trading_days" label="交易日总数" width="110" sortable>
              <template #default="{ row }">{{ row.tradingDays != null ? formatNumber(row.tradingDays) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="trading_days_2026" label="2026交易日" width="100">
              <template #default="{ row }">{{ row.tradingDays2026 || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewProductCalendar(row.product_code)">查看日历</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 2: 日历浏览 ===== -->
      <el-tab-pane label="日历浏览" name="browse">
        <el-card>
          <!-- 筛选条件 -->
          <el-form :inline="true" class="search-form">
            <el-form-item label="范围">
              <el-select v-model="browseScope" style="width:140px">
                <el-option label="交易所 (ALL)" value="exchange" />
                <el-option label="产品" value="product" />
              </el-select>
            </el-form-item>
            <el-form-item label="交易所" v-if="browseScope === 'exchange'">
              <el-select v-model="browseExchange" style="width:120px">
                <el-option label="全部" value="ALL" />
              </el-select>
            </el-form-item>
            <el-form-item label="商品" v-if="browseScope === 'product'">
              <el-select v-model="browseProduct" style="width:140px">
                <el-option-group label="期货">
                  <el-option v-for="p in allFutureProducts" :key="p.product_code" :label="p.product_name || p.product_code" :value="p.product_code" />
                </el-option-group>
                <el-option-group label="期权">
                  <el-option v-for="p in allOptionProducts" :key="p.product_code" :label="p.product_name || p.product_code" :value="p.product_code" />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item label="年月">
              <el-date-picker v-model="browseMonth" type="month" placeholder="选择月份" value-format="YYYY-MM" style="width:140px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadBrowseCalendar">查看</el-button>
            </el-form-item>
          </el-form>

          <!-- 月历显示 -->
          <div v-if="browseMonthData" class="browse-calendar">
            <div class="month-card-large">
              <div class="month-title-large">{{ browseMonthData.monthTitle }}</div>
              <div class="week-header">
                <span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span class="we">周六</span><span class="we">周日</span>
              </div>
              <div class="week-body">
                <div v-for="i in browseMonthData.padding" :key="'p' + i" class="day-cell empty"></div>
                <div v-for="day in browseMonthData.days" :key="day.date"
                     :class="['day-cell', dayClass(day)]"
                     :title="dayTooltip(day)">
                  <span class="day-num">{{ day.day }}</span>
                  <span v-if="day.holiday_name" class="day-label">{{ day.holiday_name }}</span>
                </div>
              </div>
            </div>
          </div>

          <el-empty v-else description="请选择年月查看日历" :image-size="120" />

          <!-- 图例 -->
          <div class="legend">
            <span class="legend-item"><span class="legend-dot trading"></span>交易日</span>
            <span class="legend-item"><span class="legend-dot weekend"></span>周末</span>
            <span class="legend-item"><span class="legend-dot holiday"></span>节假日</span>
            <span class="legend-item"><span class="legend-dot not-listed"></span>未上市</span>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 3: 列表查询 ===== -->
      <el-tab-pane label="列表查询" name="list">
        <el-card>
          <el-form :inline="true" class="search-form">
            <el-form-item label="日期范围">
              <el-date-picker v-model="dateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="交易所">
              <el-select v-model="exchangeCode" placeholder="全部" style="width:120px">
                <el-option label="全部" value="ALL" />
                <el-option v-for="ex in exchanges" :key="ex.exchange_code" :label="ex.exchange_code" :value="ex.exchange_code" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadCalendar">查询</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="calendarData" stripe v-loading="loading" style="margin-top:16px">
            <el-table-column prop="trade_date" label="日期" width="140" sortable />
            <el-table-column label="类型" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.is_weekend" type="info" size="small">周末</el-tag>
                <el-tag v-else-if="row.is_holiday && row.holiday_name" type="danger" size="small">{{ row.holiday_name }}</el-tag>
                <el-tag v-else-if="row.is_trading" type="success" size="small">交易日</el-tag>
                <el-tag v-else type="warning" size="small">非交易日</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="holiday_name" label="备注" width="120">
              <template #default="{ row }">
                {{ row.holiday_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="exchange_code" label="交易所" width="100" />
          </el-table>

          <div class="pagination">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[50, 100, 200]"
              layout="total, sizes, prev, pager, next"
              @size-change="loadCalendar"
              @current-change="loadCalendar"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ===== Tab 4: 商品日历 ===== -->
      <el-tab-pane label="商品日历" name="product">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>商品维度交易日历</span>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="search-form">
            <el-form-item label="交易所">
              <el-select v-model="productCalForm.exchange" style="width:120px" @change="onProductExchangeChange">
                <el-option label="中金所" value="CFFEX" />
                <el-option label="上期所" value="SHFE" />
              </el-select>
            </el-form-item>
            <el-form-item label="商品">
              <el-select v-model="productCalForm.product" style="width:160px" filterable>
                <el-option-group label="期货">
                  <el-option v-for="p in productCalForm.futuresList" :key="p.product_code" :label="`${p.product_code} ${p.product_name || ''}`" :value="p.product_code" />
                </el-option-group>
                <el-option-group label="期权">
                  <el-option v-for="p in productCalForm.optionsList" :key="p.product_code" :label="`${p.product_code} ${p.product_name || ''}`" :value="p.product_code" />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item label="年份">
              <el-select v-model="productCalForm.year" style="width:100px">
                <el-option v-for="y in productCalForm.yearOptions" :key="y" :label="y" :value="y" />
              </el-select>
            </el-form-item>
            <el-form-item label="视图">
              <el-radio-group v-model="productCalForm.viewMode" size="small">
                <el-radio-button value="month">月</el-radio-button>
                <el-radio-button value="week">周</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadProductCalendar" :loading="productCalLoading">查询</el-button>
            </el-form-item>
          </el-form>

          <!-- 商品信息 -->
          <el-descriptions v-if="productCalProductInfo" :column="3" border size="small" class="product-info-desc">
            <el-descriptions-item label="商品代码">{{ productCalForm.product }}</el-descriptions-item>
            <el-descriptions-item label="上市日期">{{ productCalProductInfo.listing_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="年内交易日">{{ productCalTradingDays.length }} / {{ productCalTotalDays }}</el-descriptions-item>
          </el-descriptions>

          <!-- 月视图 -->
          <div v-if="productCalForm.viewMode === 'month' && productCalMonthData" class="product-calendar-month">
            <div v-for="month in productCalMonthData" :key="month.month" class="month-block">
              <div class="month-title">{{ productCalForm.year }}年{{ month.month }}月</div>
              <div class="week-header">
                <span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span class="we">六</span><span class="we">日</span>
              </div>
              <div class="week-body">
                <div v-for="n in month.padding" :key="'p'+n" class="day-cell empty"></div>
                <div v-for="day in month.days" :key="day.date"
                     :class="['day-cell', dayClass(day)]"
                     :title="dayTooltip(day)">
                  <span class="day-num">{{ day.day }}</span>
                  <span v-if="day.holiday_name && !day.is_weekend" class="day-label">{{ day.holiday_name }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 周视图 -->
          <div v-if="productCalForm.viewMode === 'week' && productCalWeekData.length > 0" class="product-calendar-week">
            <el-table :data="productCalWeekData" stripe size="small">
              <el-table-column label="周次" width="80" align="center">
                <template #default="{ row }">W{{ row.weekNum }}</template>
              </el-table-column>
              <el-table-column label="周一" align="center"><template #default="{ row }"><el-tag v-if="row.mon" :type="row.monT ? 'success' : 'danger'" size="small">{{ row.mon }} {{ row.monT ? '开' : '休' }}</el-tag></template></el-table-column>
              <el-table-column label="周二" align="center"><template #default="{ row }"><el-tag v-if="row.tue" :type="row.tueT ? 'success' : 'danger'" size="small">{{ row.tue }} {{ row.tueT ? '开' : '休' }}</el-tag></template></el-table-column>
              <el-table-column label="周三" align="center"><template #default="{ row }"><el-tag v-if="row.wed" :type="row.wedT ? 'success' : 'danger'" size="small">{{ row.wed }} {{ row.wedT ? '开' : '休' }}</el-tag></template></el-table-column>
              <el-table-column label="周四" align="center"><template #default="{ row }"><el-tag v-if="row.thu" :type="row.thuT ? 'success' : 'danger'" size="small">{{ row.thu }} {{ row.thuT ? '开' : '休' }}</el-tag></template></el-table-column>
              <el-table-column label="周五" align="center"><template #default="{ row }"><el-tag v-if="row.fri" :type="row.friT ? 'success' : 'danger'" size="small">{{ row.fri }} {{ row.friT ? '开' : '休' }}</el-tag></template></el-table-column>
              <el-table-column label="周六" align="center"><template #default="{ row }"><el-tag v-if="row.sat" type="info" size="small">{{ row.sat }} 休</el-tag></template></el-table-column>
              <el-table-column label="周日" align="center"><template #default="{ row }"><el-tag v-if="row.sun" type="info" size="small">{{ row.sun }} 休</el-tag></template></el-table-column>
            </el-table>
          </div>

          <el-empty v-if="!productCalLoading && productCalForm.product && !productCalMonthData && productCalQueried" description="未找到该商品的日历数据，请先运行系统初始化" :image-size="100" />

          <!-- 图例 -->
          <div class="legend">
            <span class="legend-item"><span class="legend-dot trading"></span>交易日</span>
            <span class="legend-item"><span class="legend-dot weekend"></span>周末</span>
            <span class="legend-item"><span class="legend-dot holiday"></span>节假日</span>
            <span class="legend-item"><span class="legend-dot not-listed"></span>未上市</span>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加节假日对话框 -->
    <el-dialog v-model="holidayDialogVisible" title="添加/标记节假日" width="400px">
      <el-form :model="holidayForm" label-width="80px">
        <el-form-item label="日期">
          <el-date-picker v-model="holidayForm.date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="交易所">
          <el-select v-model="holidayForm.exchange_code" style="width:100%">
            <el-option label="全部" value="ALL" />
            <el-option v-for="ex in exchanges" :key="ex.exchange_code" :label="ex.exchange_code" :value="ex.exchange_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="节假日名">
          <el-input v-model="holidayForm.name" placeholder="如：春节" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="holidayDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitHoliday">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'
import { formatNumber } from '../utils/format'

// ===== State =====
const route = useRoute()
const router = useRouter()
const activeTab = ref('exchange')
const loading = ref(false)
const initLoading = ref(false)

// Exchange tab
const statusData = ref({ yearRange: '', exchangeRecords: 0, productCount: 0, totalRecords: 0 })
const productOverview = ref([])
const allFutureProducts = ref([])
const allOptionProducts = ref([])

// Browse tab
const browseScope = ref('product')
const browseExchange = ref('ALL')
const browseProduct = ref('IM')
const browseMonth = ref('')
const browseMonthData = ref(null)

// List tab
const calendarData = ref([])
const exchanges = ref([])
const dateRange = ref([])
const exchangeCode = ref('ALL')
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)
const holidayDialogVisible = ref(false)
const holidayForm = ref({ date: '', exchange_code: 'ALL', name: '' })

// === Product Calendar Tab ===
const productCalForm = reactive({
  exchange: 'CFFEX',
  product: 'IF',
  year: new Date().getFullYear(),
  viewMode: 'month',
  futuresList: [],
  optionsList: [],
  yearOptions: Array.from({ length: 10 }, (_, i) => 2026 + i)
})
const productCalLoading = ref(false)
const productCalMonthData = ref(null)
const productCalWeekData = ref([])
const productCalProductInfo = ref(null)
const productCalTradingDays = ref([])
const productCalQueried = ref(false)

// 商品上市日期
const listingDates = computed(() => {
  const d = {}
  // From product overview data
  for (const p of productOverview.value) {
    if (p.listing_date) d[p.product_code] = p.listing_date
  }
  // Hardcode CFFEX products
  const defaults = {
    IF: '2010-04-16', IH: '2015-04-16', IC: '2015-04-17', IM: '2022-07-22',
    HO: '2022-07-22', FO: '2022-07-22', MO: '2022-07-22'
  }
  return { ...defaults, ...d }
})

const productCalTotalDays = computed(() => {
  const y = productCalForm.year
  return ((y % 4 === 0 && y % 100 !== 0) || y % 400 === 0) ? 366 : 365
})

// ===== Methods =====

// --- System Init ---
const systemInit = async () => {
  initLoading.value = true
  try {
    const res = await axios.post('/api/maintenance/trade-calendar/system-init', null, {
      params: { year_end: 2026 }
    })
    const d = res.data.data
    ElMessage.success(`系统初始化完成：${d.years}年，${d.exchange_calendar}条交易所记录，${Object.keys(d.products || {}).length}个产品`)
    checkStatus()
  } catch {
    ElMessage.error('系统初始化失败')
  } finally {
    initLoading.value = false
  }
}

// --- Status Check ---
const checkStatus = async () => {
  loading.value = true
  try {
    // Get exchange calendar stats
    const [statusRes, listingRes, productsRes, exchangesRes] = await Promise.all([
      axios.get('/api/maintenance/trade-calendar/status').catch(() => null),
      axios.get('/api/maintenance/trade-calendar/product/listing-dates').catch(() => null),
      axios.get('/api/maintenance/products').catch(() => null),
      axios.get('/api/maintenance/exchanges').catch(() => null),
    ])

    // Manual stats query if status endpoint doesn't exist
    if (!statusRes) {
      const [countRes] = await Promise.all([
        axios.get('/api/maintenance/trade-calendar/count').catch(() => null),
      ])
      if (countRes && countRes.data) {
        statusData.value = {
          yearRange: `${countRes.data.year_start}-${countRes.data.year_end}`,
          exchangeRecords: countRes.data.exchange_count || 0,
          productCount: countRes.data.product_count || 0,
          totalRecords: countRes.data.total_count || 0,
        }
      }
    } else if (statusRes.data) {
      const d = statusRes.data.data || statusRes.data
      statusData.value = {
        yearRange: d.year_range || `${d.year_start}-${d.year_end}`,
        exchangeRecords: d.exchange_records || d.exchange_count,
        productCount: d.product_count,
        totalRecords: d.total_records || d.total_count,
      }
    }

    listingDates.value = listingRes?.data?.data || {}
    const allProducts = productsRes?.data?.data || []
    allFutureProducts.value = allProducts.filter(p => p.product_type !== 'option')
    allOptionProducts.value = allProducts.filter(p => p.product_type === 'option')
    exchanges.value = exchangesRes?.data?.data || []

    // Build product overview
    const cffexProducts = allProducts.filter(p => p.exchange_code === 'CFFEX')
    productOverview.value = cffexProducts.map(p => ({
      product_code: p.product_code,
      product_name: p.product_name,
      product_type: p.product_type === 'option' ? '期权' : '期货',
      listing_date: listingDates.value[p.product_code] || '',
      dateRange: '',
      tradingDays: null,
      tradingDays2026: '',
    }))

    // Fetch product calendar stats
    for (const item of productOverview.value) {
      try {
        const res = await axios.get('/api/maintenance/trade-calendar/product/stats', {
          params: { product_code: item.product_code }
        })
        if (res.data) {
          item.dateRange = `${res.data.min_date || ''} ~ ${res.data.max_date || ''}`
          item.tradingDays = res.data.trading_days_total || 0
          item.tradingDays2026 = res.data.trading_days_2026 || ''
        }
      } catch {}
    }
  } catch {
    ElMessage.error('加载状态失败')
  } finally {
    loading.value = false
  }
}

// --- Browse Calendar ---
const loadBrowseCalendar = async () => {
  if (!browseMonth.value) {
    ElMessage.warning('请选择年月')
    return
  }
  loading.value = true
  try {
    const [year, month] = browseMonth.value.split('-').map(Number)
    let data

    if (browseScope.value === 'product') {
      const res = await axios.get('/api/maintenance/trade-calendar/calendar', {
        params: { year, exchange_code: 'ALL' }
      })
      // For product view, we need product-specific data
      const months = res.data.data?.months || []
      const monthData = months.find(m => m.month === month)
      if (monthData) {
        browseMonthData.value = {
          monthTitle: `${year}年${month}月 ${browseProduct.value || ''}`,
          padding: monthData.first_weekday,
          days: monthData.days.map(d => {
            // 前端防御性校验：周末必须正确标记（使用本地时间解析）
            const dow = getDayOfWeek(d.date)
            if (dow === 0 || dow === 6) {
              d.is_weekend = true
              d.is_trading = false
            }
            // 产品维度：上市前的日期标记为未上市
            const listingDate = listingDates.value[browseProduct.value]
            if (listingDate && d.date < listingDate) {
              return { ...d, is_not_listed: true, is_trading: false, holiday_name: '未上市' }
            }
            return d
          }),
        }
      } else {
        browseMonthData.value = null
      }
    } else {
      const res = await axios.get('/api/maintenance/trade-calendar/calendar', {
        params: { year, exchange_code: browseExchange.value }
      })
      const months = res.data.data?.months || []
      const monthData = months.find(m => m.month === month)
      if (monthData) {
        browseMonthData.value = {
          monthTitle: `${year}年${month}月 交易所`,
          padding: monthData.first_weekday,
          days: monthData.days.map(d => {
            // 前端防御性校验：周末必须正确标记（使用本地时间解析）
            const dow = getDayOfWeek(d.date)
            if (dow === 0 || dow === 6) {
              d.is_weekend = true
              d.is_trading = false
            }
            return d
          }),
        }
      } else {
        browseMonthData.value = null
      }
    }
  } catch {
    ElMessage.error('加载日历失败')
  } finally {
    loading.value = false
  }
}

// --- List Tab ---
const loadCalendar = async () => {
  loading.value = true
  try {
    const startDate = dateRange.value?.[0] || '2025-01-01'
    const endDate = dateRange.value?.[1] || '2026-12-31'
    const res = await axios.get('/api/maintenance/trade-calendar/trading-days', {
      params: { start_date: startDate, end_date: endDate, exchange_code: exchangeCode.value }
    })
    const allDays = res.data.data || []
    const tradingSet = new Set(allDays)
    const fullDates = []

    // 使用本地时间构造日期，避免 new Date("YYYY-MM-DD") 的 UTC 时区偏移
    const [sy, sm, sd] = startDate.split('-').map(Number)
    const [ey, em, ed] = endDate.split('-').map(Number)
    const start = new Date(sy, sm - 1, sd)
    const end = new Date(ey, em - 1, ed)
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const dateStr = toLocalDateString(d)
      const dow = d.getDay()
      const isWeekend = dow === 0 || dow === 6
      const isHoliday = tradingSet.has(dateStr) === false && isWeekend
      fullDates.push({
        trade_date: dateStr,
        is_trading: tradingSet.has(dateStr),
        is_weekend: isWeekend,
        is_holiday: isHoliday,
        holiday_name: isWeekend ? '周末' : '',
        exchange_code: exchangeCode.value
      })
    }
    calendarData.value = fullDates
    total.value = fullDates.length
  } catch {
    ElMessage.error('加载交易日历失败')
  } finally {
    loading.value = false
  }
}

const viewProductCalendar = (productCode) => {
  browseScope.value = 'product'
  browseProduct.value = productCode
  browseMonth.value = '2026-01'
  activeTab.value = 'browse'
  nextTick(() => loadBrowseCalendar())
}

// 从 YYYY-MM-DD 字符串获取星期几（避免 new Date("YYYY-MM-DD") 的 UTC 时区偏移）
const getDayOfWeek = (dateStr) => {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).getDay() // 使用本地时间解析
}

// 将本地 Date 对象转为 YYYY-MM-DD 字符串（避免 toISOString 的 UTC 偏移）
const toLocalDateString = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

const dayClass = (day) => {
  // 优先使用 day 对象上已有的 is_weekend 标记（数据生成时已正确设置）
  if (day.is_weekend) return 'weekend'
  // 防御性：前端重新计算星期（使用本地时间解析，避免 UTC 时区偏移）
  const dow = getDayOfWeek(day.date)
  if (dow === 0 || dow === 6) return 'weekend'
  if (day.is_not_listed) return 'not-listed'
  if (day.is_holiday && day.holiday_name) return 'holiday'
  if (day.is_trading) return 'trading'
  return 'holiday'
}

const dayTooltip = (day) => {
  const dow = getDayOfWeek(day.date)
  const isWeekend = dow === 0 || dow === 6
  if (isWeekend) return `${day.date} 周末（非交易日）`
  if (day.is_not_listed) return `${day.date} 未上市`
  if (day.holiday_name) return `${day.date} ${day.holiday_name}`
  return `${day.date} ${day.is_trading ? '交易日' : '非交易日'}`
}

// --- Holiday Dialog ---
const submitHoliday = async () => {
  if (!holidayForm.value.date || !holidayForm.value.name) {
    ElMessage.warning('请填写日期和节假日名称')
    return
  }
  try {
    await axios.post('/api/maintenance/trade-calendar/add-holiday', null, {
      params: {
        trade_date: holidayForm.value.date,
        holiday_name: holidayForm.value.name,
        exchange_code: holidayForm.value.exchange_code
      }
    })
    ElMessage.success('添加成功')
    holidayDialogVisible.value = false
    loadCalendar()
  } catch {
    ElMessage.error('添加失败')
  }
}

// === Product Calendar Methods ===

const onProductExchangeChange = () => {
  productCalForm.product = 'IF'
}

const buildProductMonthData = (days, listingDate) => {
  const months = []
  const dayMap = {}
  for (const d of days) {
    dayMap[d.date] = d
  }

  const year = productCalForm.year
  for (let month = 1; month <= 12; month++) {
    const firstDay = new Date(year, month - 1, 1)
    const lastDay = new Date(year, month, 0)
    const monthDays = []
    let current = new Date(year, month - 1, 1)
    while (current <= lastDay) {
      const dateStr = toLocalDateString(current)
      let d = dayMap[dateStr]
      if (!d) {
        // Date not in API response - compute locally
        const dow = current.getDay()
        const isWeekend = dow === 0 || dow === 6
        const isBeforeListing = listingDate && dateStr < listingDate
        d = {
          date: dateStr,
          day: current.getDate(),
          is_weekend: isWeekend,
          is_trading: !isWeekend && !isBeforeListing,
          is_holiday: isWeekend || isBeforeListing,
          is_not_listed: isBeforeListing,
          holiday_name: isWeekend ? '' : (isBeforeListing ? '未上市' : ''),
        }
      }
      // Ensure weekends are marked correctly (defense in depth)
      const dow = current.getDay()
      if (dow === 0 || dow === 6) {
        d.is_weekend = true
        d.is_trading = false
      }
      monthDays.push(d)
      current.setDate(current.getDate() + 1)
    }
    // Monday=0 for CSS grid
    let firstWeekday = firstDay.getDay()
    firstWeekday = firstWeekday === 0 ? 6 : firstWeekday - 1
    months.push({ month, days: monthDays, padding: firstWeekday })
  }
  return months
}

const buildProductWeekData = (days, listingDate) => {
  const year = productCalForm.year
  const dayMap = {}
  for (const d of days) dayMap[d.date] = d

  const rows = []
  let weekNum = 1
  let d = new Date(year, 0, 1)
  while (d.getDay() !== 1) d.setDate(d.getDate() + 1)
  const endDate = new Date(year, 11, 31)

  while (d <= endDate) {
    const weekDays = []
    for (let i = 0; i < 7; i++) {
      const dd = new Date(d.getTime() + i * 86400000)
      const dateStr = dtoLocalDateString(d)
      let day = dayMap[dateStr]
      if (!day) {
        const dow = dd.getDay()
        const isWeekend = dow === 0 || dow === 6
        const isBeforeListing = listingDate && dateStr < listingDate
        day = {
          date: dateStr, is_weekend: isWeekend, is_trading: !isWeekend && !isBeforeListing,
          is_not_listed: isBeforeListing,
        }
      }
      weekDays.push(day)
    }
    const fmt = (dd) => `${String(dd.getMonth()+1).padStart(2,'0')}/${String(dd.getDate()).padStart(2,'0')}`
    rows.push({
      weekNum,
      start: fmt(weekDays[0]), end: fmt(weekDays[4]),
      mon: fmt(weekDays[0]), monT: weekDays[0].is_trading,
      tue: fmt(weekDays[1]), tueT: weekDays[1].is_trading,
      wed: fmt(weekDays[2]), wedT: weekDays[2].is_trading,
      thu: fmt(weekDays[3]), thuT: weekDays[3].is_trading,
      fri: fmt(weekDays[4]), friT: weekDays[4].is_trading,
      sat: fmt(weekDays[5]), sun: fmt(weekDays[6]),
    })
    weekNum++
    d.setDate(d.getDate() + 7)
  }
  return rows
}

const loadProductCalendar = async () => {
  if (!productCalForm.product) {
    ElMessage.warning('请选择商品')
    return
  }
  productCalLoading.value = true
  productCalQueried.value = true
  try {
    const year = productCalForm.year
    const startDate = `${year}-01-01`
    const endDate = `${year}-12-31`

    // Fetch product trading days
    const res = await axios.get('/api/maintenance/trade-calendar/product/trading-days', {
      params: { product_code: productCalForm.product, start_date: startDate, end_date: endDate }
    })
    const tradingDays = res.data.data || []
    productCalTradingDays.value = tradingDays
    const tradingSet = new Set(tradingDays)

    // Build calendar data
    const listingDate = listingDates.value[productCalForm.product]

    // Generate all days for the year
    const allDays = []
    let current = new Date(year, 0, 1)
    const yearEnd = new Date(year, 11, 31)
    while (current <= yearEnd) {
      const dateStr = toLocalDateString(current)
      const dow = current.getDay()
      const isWeekend = dow === 0 || dow === 6
      const isBeforeListing = listingDate && dateStr < listingDate
      allDays.push({
        date: dateStr,
        day: current.getDate(),
        is_weekend: isWeekend,
        is_trading: !isWeekend && !isBeforeListing && tradingSet.has(dateStr),
        is_holiday: isWeekend || isBeforeListing,
        is_not_listed: isBeforeListing,
        holiday_name: isBeforeListing ? '未上市' : '',
      })
      current.setDate(current.getDate() + 1)
    }

    productCalProductInfo.value = { listing_date: listingDate || '-' }

    if (productCalForm.viewMode === 'month') {
      productCalMonthData.value = buildProductMonthData(allDays, listingDate)
      productCalWeekData.value = []
    } else {
      productCalWeekData.value = buildProductWeekData(allDays, listingDate)
      productCalMonthData.value = null
    }
  } catch {
    ElMessage.error('加载商品日历失败')
  } finally {
    productCalLoading.value = false
  }
}

onMounted(() => {
  // 根据路由自动切换 Tab
  if (route.path === '/product-calendar') {
    activeTab.value = 'product'
  } else {
    activeTab.value = 'exchange'
  }
  const now = new Date()
  browseMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  checkStatus()
  loadCalendar()
  // 如果是商品日历路由，自动加载
  if (route.path === '/product-calendar') {
    nextTick(() => loadProductCalendar())
  }
})
</script>

<style scoped>
.page-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 8px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.status-desc { margin-bottom: 16px; }

/* Browse calendar */
.browse-calendar { display: flex; justify-content: center; margin: 24px 0; }
.month-card-large {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
  background: #fafafa;
  max-width: 600px;
  width: 100%;
}
.month-title-large {
  text-align: center;
  padding: 12px;
  font-size: 18px;
  font-weight: 600;
  background: #f0f2f5;
  border-bottom: 1px solid #ebeef5;
}

.week-header {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 13px;
  color: #999;
  padding: 8px 0;
  background: #f5f7fa;
}
.week-header .we { color: #e6a23c; }

.week-body {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  padding: 8px;
}

.day-cell {
  padding: 10px 4px;
  border-radius: 6px;
  text-align: center;
  cursor: default;
  font-size: 14px;
  min-height: 48px;
}
.day-cell.empty { visibility: hidden; }
.day-num { display: block; font-weight: 500; }
.day-label {
  display: block;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.day-cell.trading { background: #f0f9eb; color: #67c23a; }
.day-cell.weekend { background: #f5f7fa; color: #c0c4cc; }
.day-cell.holiday { background: #fef0f0; color: #f56c6c; }
.day-cell.not-listed { background: #f4f4f5; color: #909399; text-decoration: line-through; }

/* Legend */
.legend {
  display: flex;
  gap: 20px;
  margin-top: 16px;
  justify-content: center;
  font-size: 13px;
  color: #666;
}
.legend-item { display: flex; align-items: center; gap: 4px; }
.legend-dot {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  display: inline-block;
}
.legend-dot.trading { background: #f0f9eb; border: 1px solid #67c23a; }
.legend-dot.weekend { background: #f5f7fa; border: 1px solid #c0c4cc; }
.legend-dot.holiday { background: #fef0f0; border: 1px solid #f56c6c; }
.legend-dot.not-listed { background: #f4f4f5; border: 1px solid #909399; }

/* Product Calendar */
.product-info-desc { margin-bottom: 16px; }

.product-calendar-month {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  margin: 20px 0;
}

.month-block {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.month-title {
  text-align: center;
  padding: 8px;
  font-size: 13px;
  font-weight: 600;
  background: #f0f2f5;
  border-bottom: 1px solid #ebeef5;
}

.product-calendar-week {
  margin: 20px 0;
}
</style>
