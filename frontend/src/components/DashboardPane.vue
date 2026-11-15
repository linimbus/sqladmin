<template>
  <div class="dashboard">
    <section class="dash-hero">
      <div class="dash-hero-glow" />
      <div class="dash-hero-main">
        <div class="dash-kicker"><span class="live-dot" /> CONNECTED</div>
        <h1>{{ connection.name }}</h1>
        <p class="dash-hero-sub">
          {{ driverDescription }} · {{ connectionSubtitle(connection) }}
        </p>
        <div class="dash-hero-actions">
          <el-button type="primary" :icon="EditPen" @click="$emit('query')">打开 SQL 查询</el-button>
          <el-button :icon="Refresh" :loading="loadingOverview" @click="loadOverview">刷新概览</el-button>
        </div>
      </div>
      <div class="dash-hero-driver">
        <span class="driver-mark" :style="{ background: kindColor(connection.kind) }">
          {{ kindMeta(connection.kind).short }}
        </span>
        <div class="driver-copy">
          <strong>{{ kindLabel(connection.kind) }}</strong>
          <span>{{ connection.read_only ? '只读连接' : '读写连接' }}</span>
        </div>
      </div>
    </section>

    <el-alert
      v-if="overviewError"
      :title="overviewError"
      type="warning"
      show-icon
      :closable="false"
      class="dash-alert"
    />

    <section class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon tables"><el-icon><Grid /></el-icon></div>
        <div class="stat-copy">
          <span class="stat-label">数据表</span>
          <strong class="stat-value">{{ formatNumber(overview?.table_count ?? tables.length) }}</strong>
          <span class="stat-sub">张表</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon views"><el-icon><View /></el-icon></div>
        <div class="stat-copy">
          <span class="stat-label">视图</span>
          <strong class="stat-value">{{ formatNumber(overview?.view_count ?? views.length) }}</strong>
          <span class="stat-sub">个视图</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon size"><el-icon><Coin /></el-icon></div>
        <div class="stat-copy">
          <span class="stat-label">数据库大小</span>
          <strong class="stat-value">{{ overview?.size_pretty || formatBytes(overview?.size_bytes) }}</strong>
          <span class="stat-sub">当前库</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon latency"><el-icon><Timer /></el-icon></div>
        <div class="stat-copy">
          <span class="stat-label">连接延迟</span>
          <strong class="stat-value">
            {{ overview?.latency_ms !== null && overview?.latency_ms !== undefined ? `${overview.latency_ms} ms` : '—' }}
          </strong>
          <span class="stat-sub">{{ overview?.version ? `v${overview.version}` : '服务端' }}</span>
        </div>
      </div>
    </section>

    <div class="dash-columns">
      <section class="dash-card">
        <header class="dash-card-head">
          <div>
            <h3>快速访问</h3>
            <p>点击表名直接浏览数据</p>
          </div>
          <span class="dash-count">{{ tables.length }} 张表</span>
        </header>
        <div v-if="tables.length" class="quick-table-list">
          <button
            v-for="table in tables.slice(0, 14)"
            :key="table.name"
            type="button"
            class="quick-table"
            @click="$emit('select', table)"
          >
            <span class="quick-icon"><el-icon><Grid /></el-icon></span>
            <span class="quick-name">{{ table.name }}</span>
            <span v-if="table.row_estimate !== null && table.row_estimate !== undefined" class="quick-rows">
              {{ formatNumber(table.row_estimate) }} 行
            </span>
            <el-icon class="quick-arrow"><ArrowRight /></el-icon>
          </button>
        </div>
        <div v-else class="dash-empty">
          当前上下文下没有数据表
        </div>
      </section>

      <section class="dash-card">
        <header class="dash-card-head">
          <div>
            <h3>连接信息</h3>
            <p>当前会话的数据库上下文</p>
          </div>
        </header>
        <dl class="info-list">
          <div class="info-row">
            <dt>数据库类型</dt>
            <dd>{{ kindLabel(connection.kind) }}</dd>
          </div>
          <div class="info-row">
            <dt>{{ connection.kind === 'sqlite' ? '文件路径' : '主机地址' }}</dt>
            <dd class="mono">{{ connection.kind === 'sqlite' ? connection.sqlite_path : `${connection.host || '127.0.0.1'}${connection.port ? `:${connection.port}` : ''}` }}</dd>
          </div>
          <div class="info-row">
            <dt>当前数据库</dt>
            <dd class="mono">{{ database || connection.database || '默认' }}</dd>
          </div>
          <div v-if="schema" class="info-row">
            <dt>Schema</dt>
            <dd class="mono">{{ schema }}</dd>
          </div>
          <div class="info-row">
            <dt>访问模式</dt>
            <dd>
              <el-tag :type="connection.read_only ? 'warning' : 'success'" size="small" effect="plain">
                {{ connection.read_only ? '只读' : '读写' }}
              </el-tag>
            </dd>
          </div>
          <div class="info-row">
            <dt>服务端版本</dt>
            <dd class="mono">{{ overview?.version || '—' }}</dd>
          </div>
        </dl>
        <button type="button" class="dash-edit" @click="$emit('edit')">
          <el-icon><Setting /></el-icon>
          编辑连接配置
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  ArrowRight,
  Coin,
  EditPen,
  Grid,
  Refresh,
  Setting,
  Timer,
  View,
} from '@element-plus/icons-vue'
import { api } from '../api'
import {
  connectionSubtitle,
  formatBytes,
  formatNumber,
  kindColor,
  kindLabel,
  kindMeta,
} from '../utils'

const props = defineProps({
  connection: { type: Object, required: true },
  catalogs: { type: Object, default: () => ({}) },
  database: { type: String, default: null },
  schema: { type: String, default: null },
  tables: { type: Array, default: () => [] },
  views: { type: Array, default: () => [] },
})

defineEmits(['query', 'select', 'edit'])

const overview = ref(null)
const loadingOverview = ref(false)
const overviewError = ref('')

const driverDescription = computed(() => {
  const descriptions = {
    sqlite: '轻量级嵌入式数据库',
    mysql: '最流行的开源关系型数据库',
    postgresql: '功能强大的开源对象关系数据库',
    mssql: 'Microsoft 企业级数据库',
    oracle: 'Oracle 企业级数据库',
  }
  return descriptions[props.connection.kind] || '关系型数据库'
})

async function loadOverview() {
  loadingOverview.value = true
  overviewError.value = ''
  try {
    overview.value = await api.overview(
      props.connection.id,
      props.database,
      props.schema,
    )
  } catch (error) {
    overviewError.value = error.message
  } finally {
    loadingOverview.value = false
  }
}

watch(
  () => [props.connection.id, props.database, props.schema],
  () => loadOverview(),
)

onMounted(loadOverview)
</script>
