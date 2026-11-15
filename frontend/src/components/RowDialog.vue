<template>
  <el-dialog
    v-model="visible"
    :title="mode === 'create' ? `新增数据 · ${table}` : `编辑数据 · ${table}`"
    width="620px"
    top="8vh"
    destroy-on-close
    :close-on-click-modal="false"
    class="row-dialog"
    @open="init"
  >
    <div class="row-dialog-body">
      <div class="row-dialog-tip">
        <el-icon><InfoFilled /></el-icon>
        <span v-if="mode === 'create'">未勾选的字段不会写入 SQL，由数据库使用默认值或自增规则。</span>
        <span v-else>主键字段不可修改；勾选 NULL 表示将该字段置空。</span>
      </div>

      <div class="row-form-grid">
        <div
          v-for="column in visibleColumns"
          :key="column.name"
          class="row-field"
          :class="{ 'is-pk': isPrimaryKey(column.name) && mode === 'edit' }"
        >
          <div class="row-field-head">
            <span class="row-field-name">{{ column.name }}</span>
            <span class="row-field-type">{{ column.type }}</span>
            <span v-if="isPrimaryKey(column.name)" class="pk-badge">PK</span>
            <span v-if="column.autoincrement && mode === 'create'" class="auto-badge">AUTO</span>
            <span v-if="column.computed" class="auto-badge">生成列</span>
            <el-checkbox
              v-if="showNullToggle(column)"
              v-model="nullFlags[column.name]"
              size="small"
              class="null-checkbox"
            >
              {{ mode === 'create' ? '留空' : 'NULL' }}
            </el-checkbox>
          </div>

          <div v-if="mode === 'edit' && isPrimaryKey(column.name)" class="pk-value">
            {{ formatPkValue(form[column.name]) }}
          </div>
          <div v-else-if="column.computed" class="pk-value">
            {{ mode === 'edit' ? formatPkValue(form[column.name]) : '由数据库自动生成' }}
          </div>
          <template v-else>
            <el-select
              v-if="isBoolean(column)"
              v-model="form[column.name]"
              :disabled="mode === 'edit' && Boolean(nullFlags[column.name])"
              class="full-width"
              @change="nullFlags[column.name] = false"
            >
              <el-option label="true" :value="true" />
              <el-option label="false" :value="false" />
            </el-select>
            <el-input
              v-else-if="isLongText(column)"
              v-model="form[column.name]"
              type="textarea"
              :rows="3"
              :disabled="mode === 'edit' && Boolean(nullFlags[column.name])"
              :placeholder="placeholderFor(column)"
              @input="nullFlags[column.name] = false"
            />
            <el-input
              v-else
              v-model="form[column.name]"
              :disabled="mode === 'edit' && Boolean(nullFlags[column.name])"
              :placeholder="placeholderFor(column)"
              @input="nullFlags[column.name] = false"
            />
          </template>

          <div v-if="column.default" class="row-field-hint" :title="column.default">
            默认值：{{ column.default }}
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <span class="row-footer-hint">共 {{ visibleColumns.length }} 个字段</span>
        <div class="footer-right">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submit">
            {{ mode === 'create' ? '插入数据' : '保存修改' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script>
export default { name: 'RowDialog' }
</script>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { api } from '../api'

const visible = defineModel({ type: Boolean, default: false })

const props = defineProps({
  mode: { type: String, default: 'create' },
  connectionId: { type: Number, required: true },
  table: { type: String, required: true },
  columns: { type: Array, default: () => [] },
  pkNames: { type: Array, default: () => [] },
  row: { type: Array, default: null },
  database: { type: String, default: null },
  schema: { type: String, default: null },
})

const emit = defineEmits(['saved'])

const form = reactive({})
const nullFlags = reactive({})
const saving = ref(false)

const visibleColumns = computed(() => props.columns)

function isPrimaryKey(name) {
  return props.pkNames.includes(name)
}

function isBoolean(column) {
  return /^(bool|boolean|bit)$/i.test((column.type || '').replace(/\(.*\)/, '').trim())
}

function isLongText(column) {
  return /json|clob|blob|binary|bytea|xml|longtext|mediumtext/i.test(column.type || '')
}

function showNullToggle(column) {
  if (column.computed) return false
  if (props.mode === 'edit' && isPrimaryKey(column.name)) return false
  if (props.mode === 'edit') return Boolean(column.nullable)
  return Boolean(column.nullable || column.default || column.autoincrement)
}

function placeholderFor(column) {
  if (props.mode === 'create') {
    if (column.autoincrement) return '留空自动生成'
    if (column.default) return '留空使用默认值'
    return column.nullable ? '可留空（NULL）' : '必填'
  }
  return column.nullable ? 'NULL' : '必填'
}

function init() {
  for (const key of Object.keys(form)) delete form[key]
  for (const key of Object.keys(nullFlags)) delete nullFlags[key]

  if (props.mode === 'create') {
    for (const column of visibleColumns.value) {
      form[column.name] = ''
      nullFlags[column.name] = Boolean(column.autoincrement || column.default)
    }
    return
  }

  for (const column of props.columns) {
    const index = props.columns.findIndex((item) => item.name === column.name)
    const value = props.row?.[index]
    if (isBoolean(column)) {
      form[column.name] =
        value === null || value === undefined
          ? ''
          : value === true || value === 1 || String(value).toLowerCase() === 'true'
    } else {
      form[column.name] =
        value === null || value === undefined
          ? ''
          : typeof value === 'object'
            ? JSON.stringify(value)
            : value
    }
    nullFlags[column.name] = value === null || value === undefined
  }
}

function formatPkValue(value) {
  if (value === null || value === undefined || value === '') return 'NULL'
  return String(value)
}

function pkFromRow() {
  const pk = {}
  for (const name of props.pkNames) {
    const index = props.columns.findIndex((column) => column.name === name)
    pk[name] = props.row?.[index] ?? null
  }
  return pk
}

function submit() {
  const values = {}
  if (props.mode === 'create') {
    for (const column of visibleColumns.value) {
      if (column.computed) continue
      if (nullFlags[column.name]) {
        if (!column.nullable && !column.default && !column.autoincrement) {
          ElMessage.warning(`字段 ${column.name} 为必填`)
          return
        }
        continue
      }
      const value = form[column.name]
      if (value === '' && !column.nullable) {
        ElMessage.warning(`字段 ${column.name} 不能为空`)
        return
      }
      values[column.name] = value === '' ? null : value
    }
  } else {
    for (const column of props.columns) {
      if (isPrimaryKey(column.name) || column.computed) continue
      values[column.name] = nullFlags[column.name] ? null : form[column.name] === '' ? null : form[column.name]
    }
  }

  saving.value = true
  const request =
    props.mode === 'create'
      ? api.insertRow(props.connectionId, props.table, values, props.database, props.schema)
      : api.updateRow(
          props.connectionId,
          props.table,
          pkFromRow(),
          values,
          props.database,
          props.schema,
        )

  request
    .then(() => {
      ElMessage.success(props.mode === 'create' ? '数据已插入' : '修改已保存')
      visible.value = false
      emit('saved')
    })
    .catch((error) => ElMessage.error(error.message))
    .finally(() => {
      saving.value = false
    })
}
</script>
