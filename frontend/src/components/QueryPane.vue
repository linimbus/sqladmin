<template>
  <div class="query-pane">
    <div class="query-toolbar">
      <div class="qt-left">
        <div class="qt-context">
          <span class="ctx-dot" :style="{ background: kindColor(connection.kind) }" />
          <span class="ctx-name">{{ connection.name }}</span>
          <el-tag size="small" effect="plain">{{ kindLabel(connection.kind) }}</el-tag>
          <el-tag v-if="connection.read_only" size="small" type="warning" effect="plain">只读</el-tag>
        </div>
        <el-select
          v-if="showDatabase"
          v-model="database"
          size="small"
          placeholder="数据库"
          class="ctx-select"
          @change="onDatabaseChange"
        >
          <el-option v-for="name in localCatalogs.databases || []" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select
          v-if="showSchema"
          v-model="schema"
          size="small"
          placeholder="Schema"
          class="ctx-select"
          @change="loadCompletion"
        >
          <el-option v-for="name in localCatalogs.schemas || []" :key="name" :label="name" :value="name" />
        </el-select>
      </div>

      <div class="qt-right">
        <span class="shortcut-hint">⌘ / Ctrl + Enter</span>
        <el-select v-model="maxRows" size="small" class="max-rows-select">
          <el-option label="最多 100 行" :value="100" />
          <el-option label="最多 500 行" :value="500" />
          <el-option label="最多 1000 行" :value="1000" />
          <el-option label="最多 5000 行" :value="5000" />
        </el-select>
        <el-button type="primary" :icon="VideoPlay" :loading="running" @click="run">
          运行
        </el-button>
      </div>
    </div>

    <div class="editor-panel" :style="{ height: `${editorHeight}px` }">
      <SqlEditor
        v-model="sql"
        :dialect="connection.kind"
        :schema="completion"
        @run="run"
      />
      <div class="editor-resizer" title="拖动调整编辑器高度" @mousedown.prevent="startResize" />
    </div>

    <div class="query-result">
      <div class="result-head">
        <div class="result-tabs">
          <template v-if="results.length">
            <button
              v-for="(result, index) in results"
              :key="index"
              :class="['result-tab', { active: activeResult === index }]"
              @click="activeResult = index"
            >
              <span class="result-dot" :class="result.error ? 'error' : 'ok'" />
              结果 {{ index + 1 }}
              <span class="result-type">{{ result.type }}</span>
            </button>
          </template>
          <span v-else class="result-title">执行结果</span>
        </div>
        <div v-if="currentResult" class="result-actions">
          <template v-if="currentResult.columns.length">
            <el-button link size="small" :icon="CopyDocument" @click="copyResult">复制</el-button>
            <el-button link size="small" :icon="Download" @click="downloadResult">导出</el-button>
          </template>
          <span class="result-meta">
            <template v-if="currentResult.columns.length">
              {{ formatNumber(currentResult.rows.length) }} 行 ·
            </template>
            {{ currentResult.duration_ms }} ms
          </span>
        </div>
      </div>

      <div class="result-body">
        <div v-if="running" class="query-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在执行 SQL…</span>
        </div>

        <el-alert
          v-else-if="requestError"
          type="error"
          :title="requestError"
          show-icon
          :closable="false"
          class="result-alert"
        />

        <template v-else-if="response">
          <template v-if="currentResult">
            <el-alert
              v-if="currentResult.truncated"
              type="warning"
              :closable="false"
              show-icon
              class="result-alert"
              :title="`结果已截断，仅显示前 ${maxRows} 行`"
            />
            <el-alert
              v-if="currentResult.error"
              type="error"
              :title="'SQL 执行失败'"
              :description="currentResult.error"
              show-icon
              :closable="false"
              class="result-alert sql-error"
            />
            <div v-else-if="currentResult.columns.length" class="result-grid-wrap">
              <DataGrid
                :columns="currentResult.columns"
                :rows="currentResult.rows"
                :sortable="false"
                :show-index="true"
                empty-text="查询执行成功，但没有返回数据"
              />
            </div>
            <div v-else class="mutation-success">
              <div class="success-icon"><el-icon><CircleCheck /></el-icon></div>
              <h3>语句执行成功</h3>
              <p>
                <span class="type-chip">{{ currentResult.type }}</span>
                <template v-if="currentResult.row_count !== null && currentResult.row_count !== undefined">
                  影响 {{ formatNumber(currentResult.row_count) }} 行
                </template>
                <template v-else>数据库未返回受影响行数</template>
                <span class="dot-sep">·</span>
                耗时 {{ currentResult.duration_ms }} ms
              </p>
              <p class="muted">共执行 {{ results.length }} 条语句，总耗时 {{ response.duration_ms }} ms</p>
            </div>
          </template>
        </template>

        <div v-else class="query-hint">
          <div class="hint-icon"><el-icon><MagicStick /></el-icon></div>
          <h3>准备就绪</h3>
          <p>在上方编辑器中输入 SQL，按 <kbd>⌘</kbd> / <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 执行</p>
          <div class="quick-examples">
            <button type="button" @click="useExample('SELECT 1;')">
              测试查询 <code>SELECT 1;</code>
            </button>
            <button v-if="firstTable" type="button" @click="useExample(`SELECT * FROM ${firstTable} LIMIT 100;`)">
              预览 {{ firstTable }} <code>SELECT * …</code>
            </button>
            <button v-if="firstTable" type="button" @click="useExample(`SELECT COUNT(*) FROM ${firstTable};`)">
              统计行数 <code>COUNT(*)</code>
            </button>
          </div>
          <p v-if="connection.read_only" class="hint-readonly">
            <el-icon><Lock /></el-icon>
            只读连接仅允许执行查询语句
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  CopyDocument,
  Download,
  Loading,
  Lock,
  MagicStick,
  VideoPlay,
} from '@element-plus/icons-vue'
import { api } from '../api'
import {
  copyToClipboard,
  downloadCsv,
  formatNumber,
  kindColor,
  kindLabel,
} from '../utils'
import DataGrid from './DataGrid.vue'
import SqlEditor from './SqlEditor.vue'

const props = defineProps({
  tab: { type: Object, required: true },
  connection: { type: Object, required: true },
  catalogs: { type: Object, default: () => ({}) },
})

const storageKey = `sql-station:${props.tab.connectionId}:${props.tab.key}`
const sql = ref(sessionStorage.getItem(storageKey) || '')
const maxRows = ref(500)
const running = ref(false)
const response = ref(null)
const requestError = ref('')
const activeResult = ref(0)
const editorHeight = ref(300)

const database = ref(props.tab.database || null)
const schema = ref(props.tab.schema || null)
const localCatalogs = ref({ ...(props.catalogs || {}) })
const completion = ref({})

const results = computed(() => response.value?.results || [])
const currentResult = computed(() => results.value[activeResult.value] || null)

const showDatabase = computed(
  () => props.connection.kind === 'mysql' || props.connection.kind === 'mssql',
)
const showSchema = computed(
  () => props.connection.kind !== 'sqlite' && (localCatalogs.value.schemas || []).length > 0,
)

const firstTable = computed(() => Object.keys(completion.value)[0] || '')

watch(sql, (value) => sessionStorage.setItem(storageKey, value))

watch(
  () => props.catalogs,
  (value) => {
    if (!value) return
    localCatalogs.value = { ...value }
    if (!database.value) {
      database.value = value.current_database || (value.databases || [])[0] || null
    }
    if (!schema.value && (value.schemas || []).length) {
      const schemas = value.schemas
      const preferred = props.connection.kind === 'mssql' ? 'dbo' : 'public'
      schema.value = schemas.includes(preferred) ? preferred : schemas[0]
    }
  },
)

async function loadCompletion() {
  try {
    completion.value = await api.completion(
      props.tab.connectionId,
      database.value,
      schema.value,
    )
  } catch {
    completion.value = {}
  }
}

async function onDatabaseChange() {
  try {
    localCatalogs.value = await api.catalogs(props.tab.connectionId, database.value)
    const schemas = localCatalogs.value.schemas || []
    schema.value = schemas.includes('dbo')
      ? 'dbo'
      : schemas.includes('public')
        ? 'public'
        : schemas[0] || null
  } catch (error) {
    ElMessage.error(error.message)
  }
  loadCompletion()
}

async function run() {
  if (!sql.value.trim()) {
    ElMessage.warning('请输入要执行的 SQL')
    return
  }
  running.value = true
  requestError.value = ''
  response.value = null
  activeResult.value = 0
  try {
    response.value = await api.query(props.tab.connectionId, {
      sql: sql.value,
      max_rows: maxRows.value,
      database: database.value,
      schema: schema.value,
    })
  } catch (error) {
    requestError.value = error.message
  } finally {
    running.value = false
  }
}

function useExample(statement) {
  sql.value = statement
}

function resultTsv() {
  if (!currentResult.value) return ''
  const header = currentResult.value.columns.map((column) => column.name).join('\t')
  const rows = currentResult.value.rows.map((row) =>
    row
      .map((value) =>
        value === null || value === undefined
          ? ''
          : typeof value === 'object'
            ? JSON.stringify(value)
            : String(value),
      )
      .join('\t'),
  )
  return [header, ...rows].join('\n')
}

async function copyResult() {
  try {
    await copyToClipboard(resultTsv())
    ElMessage.success('结果已复制为制表符分隔文本')
  } catch {
    ElMessage.error('复制失败')
  }
}

function downloadResult() {
  if (!currentResult.value) return
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  downloadCsv(`query-result-${stamp}.csv`, currentResult.value.columns, currentResult.value.rows)
}

function startResize(event) {
  const startY = event.clientY
  const startHeight = editorHeight.value
  const onMove = (moveEvent) => {
    editorHeight.value = Math.max(140, Math.min(640, startHeight + moveEvent.clientY - startY))
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    document.body.classList.remove('is-resizing')
  }
  document.body.classList.add('is-resizing')
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

onMounted(loadCompletion)
</script>
