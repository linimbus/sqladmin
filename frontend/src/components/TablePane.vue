<template>
  <div class="table-pane">
    <header class="table-pane-head">
      <div class="tp-title">
        <span class="tp-icon" :class="tab.objType === 'view' ? 'view' : 'table'">
          <el-icon><Grid /></el-icon>
        </span>
        <div class="tp-title-text">
          <div class="tp-name-row">
            <h2>{{ tab.table }}</h2>
            <el-tag size="small" effect="plain" :type="tab.objType === 'view' ? 'warning' : 'info'">
              {{ tab.objType === 'view' ? 'VIEW' : 'TABLE' }}
            </el-tag>
          </div>
          <div class="tp-sub">
            <span v-if="tab.schema">{{ tab.schema }}.</span>
            <span>{{ tab.table }}</span>
            <span v-if="rowsData" class="dot-sep">·</span>
            <span v-if="rowsData">{{ formatNumber(rowsData.total) }} 行</span>
            <span v-if="detail" class="dot-sep">·</span>
            <span v-if="detail">{{ detail.columns.length }} 个字段</span>
            <span v-if="tab.database" class="dot-sep">·</span>
            <span v-if="tab.database">库 {{ tab.database }}</span>
          </div>
        </div>
      </div>
      <div class="tp-actions">
        <el-button size="small" :icon="Refresh" :loading="loadingRows || loadingDetail" @click="refreshAll">
          刷新
        </el-button>
        <el-button size="small" :icon="Download" @click="exportCsv">导出 CSV</el-button>
        <el-button
          v-if="canEdit"
          type="primary"
          size="small"
          :icon="Plus"
          @click="openCreateRow"
        >
          新增行
        </el-button>
      </div>
    </header>

    <div class="tp-tabs">
      <button :class="['tp-tab', { active: dataTab === 'data' }]" @click="dataTab = 'data'">
        数据
      </button>
      <button :class="['tp-tab', { active: dataTab === 'structure' }]" @click="dataTab = 'structure'">
        结构
      </button>
      <div class="tp-tab-spacer" />
      <span v-if="connection.read_only" class="readonly-badge">
        <el-icon><Lock /></el-icon> 只读连接
      </span>
    </div>

    <div v-show="dataTab === 'data'" class="data-pane">
      <div class="data-toolbar">
        <el-input
          v-model="whereInput"
          size="small"
          clearable
          placeholder="WHERE 条件，例如 status = 1 AND name LIKE '%foo%'"
          class="where-input"
          @keyup.enter="applyWhere"
          @clear="applyWhere"
        >
          <template #prefix><span class="sql-prefix">WHERE</span></template>
        </el-input>
        <el-button size="small" @click="applyWhere">筛选</el-button>
        <el-button v-if="whereApplied" size="small" text @click="clearWhere">清除</el-button>
        <div class="toolbar-spacer" />
        <el-select v-model="pageSize" size="small" class="page-size-select" @change="onPageSizeChange">
          <el-option label="20 行 / 页" :value="20" />
          <el-option label="50 行 / 页" :value="50" />
          <el-option label="100 行 / 页" :value="100" />
          <el-option label="200 行 / 页" :value="200" />
        </el-select>
      </div>

      <el-alert
        v-if="rowsError"
        :title="rowsError"
        type="error"
        show-icon
        :closable="false"
        class="data-error"
      />

      <div class="grid-wrap">
        <DataGrid
          :columns="rowsData?.columns || []"
          :rows="rowsData?.rows || []"
          :loading="loadingRows"
          :editable="canEditRows"
          :start-index="(page - 1) * pageSize"
          empty-text="当前条件下没有数据"
          @sort-change="onSortChange"
          @edit="openEditRow"
          @delete="deleteRow"
        />
      </div>

      <div class="table-pagination">
        <span class="page-meta">
          共 {{ formatNumber(rowsData?.total ?? 0) }} 行
          <template v-if="rowsData?.duration_ms !== undefined">
            · {{ rowsData.duration_ms }} ms
          </template>
        </span>
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="rowsData?.total || 0"
          layout="prev, pager, next"
          background
          size="small"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <div v-show="dataTab === 'structure'" class="structure-wrap">
      <StructurePane :detail="detail" :loading="loadingDetail" />
    </div>

    <RowDialog
      v-model="rowDialogVisible"
      :mode="rowDialogMode"
      :connection-id="tab.connectionId"
      :table="tab.table"
      :columns="detail?.columns || rowsData?.columns || []"
      :pk-names="detail?.primary_key || rowsData?.primary_key || []"
      :row="editingRow"
      :database="tab.database"
      :schema="tab.schema"
      @saved="onRowSaved"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Grid, Lock, Plus, Refresh } from '@element-plus/icons-vue'
import { api } from '../api'
import { formatNumber } from '../utils'
import DataGrid from './DataGrid.vue'
import RowDialog from './RowDialog.vue'
import StructurePane from './StructurePane.vue'

const props = defineProps({
  tab: { type: Object, required: true },
  connection: { type: Object, required: true },
})

const dataTab = ref('data')
const detail = ref(null)
const rowsData = ref(null)
const loadingRows = ref(false)
const loadingDetail = ref(false)
const rowsError = ref('')

const page = ref(1)
const pageSize = ref(50)
const orderBy = ref(null)
const orderDir = ref('asc')

const whereInput = ref('')
const whereApplied = ref('')

const rowDialogVisible = ref(false)
const rowDialogMode = ref('create')
const editingRow = ref(null)

const canEdit = computed(
  () => !props.connection.read_only && props.tab.objType !== 'view' && detail.value?.type !== 'view',
)

const canEditRows = computed(
  () => canEdit.value && (detail.value?.primary_key?.length || 0) > 0,
)

async function loadDetail() {
  loadingDetail.value = true
  try {
    detail.value = await api.tableDetail(
      props.tab.connectionId,
      props.tab.table,
      props.tab.database,
      props.tab.schema,
    )
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loadingDetail.value = false
  }
}

async function loadRows() {
  loadingRows.value = true
  rowsError.value = ''
  try {
    rowsData.value = await api.rows(props.tab.connectionId, props.tab.table, {
      database: props.tab.database,
      schema: props.tab.schema,
      page: page.value,
      page_size: pageSize.value,
      order_by: orderBy.value,
      order_dir: orderDir.value,
      where: whereApplied.value,
    })
  } catch (error) {
    rowsError.value = error.message
  } finally {
    loadingRows.value = false
  }
}

function refreshAll() {
  loadDetail()
  loadRows()
}

function onPageChange(nextPage) {
  page.value = nextPage
  loadRows()
}

function onPageSizeChange() {
  page.value = 1
  loadRows()
}

function onSortChange({ name, order }) {
  if (!order) {
    orderBy.value = null
    orderDir.value = 'asc'
  } else {
    orderBy.value = name
    orderDir.value = order
  }
  page.value = 1
  loadRows()
}

function applyWhere() {
  whereApplied.value = whereInput.value.trim()
  page.value = 1
  loadRows()
}

function clearWhere() {
  whereInput.value = ''
  whereApplied.value = ''
  page.value = 1
  loadRows()
}

function exportCsv() {
  const url = api.tableExportUrl(props.tab.connectionId, props.tab.table, {
    database: props.tab.database,
    schema: props.tab.schema,
    order_by: orderBy.value,
    order_dir: orderDir.value,
    where: whereApplied.value,
  })
  const link = document.createElement('a')
  link.href = url
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function openCreateRow() {
  rowDialogMode.value = 'create'
  editingRow.value = null
  rowDialogVisible.value = true
}

function openEditRow(row) {
  rowDialogMode.value = 'edit'
  editingRow.value = row
  rowDialogVisible.value = true
}

function pkFromRow(row) {
  const pk = {}
  const names = detail.value?.primary_key?.length
    ? detail.value.primary_key
    : rowsData.value?.primary_key || []
  for (const name of names) {
    const index = (rowsData.value?.columns || []).findIndex((column) => column.name === name)
    if (index >= 0) pk[name] = row[index] ?? null
  }
  return pk
}

async function deleteRow(row) {
  const pk = pkFromRow(row)
  if (!Object.keys(pk).length) {
    ElMessage.warning('该表没有主键，无法直接删除数据行')
    return
  }
  const preview = Object.entries(pk)
    .map(([key, value]) => `${key} = ${value}`)
    .join('，')
  try {
    await ElMessageBox.confirm(`确定删除主键为 ${preview} 的数据行吗？该操作不可撤销。`, '删除数据', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await api.deleteRow(
      props.tab.connectionId,
      props.tab.table,
      pk,
      props.tab.database,
      props.tab.schema,
    )
    ElMessage.success('数据已删除')
    if (page.value > 1 && rowsData.value?.rows?.length === 1) page.value -= 1
    await Promise.all([loadRows(), loadDetail()])
  } catch (error) {
    ElMessage.error(error.message)
  }
}

function onRowSaved() {
  loadRows()
  loadDetail()
}

onMounted(() => {
  loadDetail()
  loadRows()
})
</script>
