<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑连接' : '新建数据库连接'"
    width="640px"
    class="connection-dialog"
    :close-on-click-modal="false"
    destroy-on-close
    @closed="resetTest"
  >
    <el-form label-position="top" class="conn-form" @submit.prevent>
      <el-form-item label="数据库类型">
        <div class="driver-grid">
          <button
            v-for="option in DRIVER_OPTIONS"
            :key="option.value"
            type="button"
            :class="['driver-card', { active: form.kind === option.value }]"
            @click="changeKind(option.value)"
          >
            <span class="driver-badge" :style="{ background: kindColor(option.value) + '1a', color: kindColor(option.value) }">
              {{ kindMeta(option.value).short }}
            </span>
            <span>{{ option.label }}</span>
          </button>
        </div>
      </el-form-item>

      <el-form-item label="连接名称" required>
        <el-input v-model="form.name" placeholder="例如：生产订单库" maxlength="120" />
      </el-form-item>

      <template v-if="form.kind === 'sqlite'">
        <el-form-item label="数据库文件路径" required>
          <el-input v-model="form.sqlite_path" placeholder="例如：demo.db 或 /Users/me/data/demo.db">
            <template #prefix><el-icon><FolderOpened /></el-icon></template>
          </el-input>
          <div class="field-hint">相对路径会保存在后端 data 目录下；文件不存在时会自动创建。</div>
        </el-form-item>
      </template>

      <template v-else>
        <div class="form-grid">
          <el-form-item label="主机" required>
            <el-input v-model="form.host" placeholder="127.0.0.1" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" class="full-width" />
          </el-form-item>
        </div>

        <div class="form-grid">
          <el-form-item label="用户名">
            <el-input v-model="form.username" autocomplete="off" />
          </el-form-item>
          <el-form-item :label="isEdit ? '密码（留空保持不变）' : '密码'">
            <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
          </el-form-item>
        </div>

        <div class="form-grid">
          <el-form-item :label="databaseLabel">
            <el-input v-model="form.database" :placeholder="databasePlaceholder" />
          </el-form-item>
          <el-form-item v-if="form.kind === 'mysql'" label="字符集">
            <el-select v-model="form.charset" class="full-width">
              <el-option label="utf8mb4（推荐）" value="utf8mb4" />
              <el-option label="utf8" value="utf8" />
              <el-option label="latin1" value="latin1" />
            </el-select>
          </el-form-item>
        </div>
      </template>

      <el-form-item>
        <div class="readonly-row">
          <div>
            <div class="readonly-title">只读模式</div>
            <div class="field-hint">开启后禁止执行写操作，适合查看生产数据。</div>
          </div>
          <el-switch v-model="form.read_only" />
        </div>
      </el-form-item>

      <el-alert
        v-if="testResult"
        :type="testResult.ok ? 'success' : 'error'"
        :title="testResult.ok ? '连接测试成功' : '连接测试失败'"
        :description="testResult.message"
        show-icon
        :closable="false"
        class="test-result"
      />
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button :loading="testing" @click="handleTest">测试连接</el-button>
        <div class="footer-right">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">
            {{ isEdit ? '保存修改' : '创建连接' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FolderOpened } from '@element-plus/icons-vue'
import { api } from '../api'
import {
  DEFAULT_PORTS,
  DRIVER_OPTIONS,
  kindColor,
  kindMeta,
} from '../utils'

const visible = defineModel({ type: Boolean, default: false })
const props = defineProps({
  connection: { type: Object, default: null },
})
const emit = defineEmits(['saved'])

const isEdit = computed(() => Boolean(props.connection?.id))
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)

const form = reactive({
  name: '',
  kind: 'sqlite',
  host: '127.0.0.1',
  port: null,
  username: '',
  password: '',
  database: '',
  sqlite_path: '',
  charset: 'utf8mb4',
  read_only: false,
})

const databaseLabel = computed(() => {
  if (form.kind === 'oracle') return '服务名 / SID'
  return '默认数据库'
})

const databasePlaceholder = computed(() => {
  if (form.kind === 'postgresql') return '例如：postgres'
  if (form.kind === 'mysql') return '可留空，连接后选择'
  if (form.kind === 'oracle') return '例如：ORCL'
  return '可留空，连接后选择'
})

function fillForm(connection) {
  testResult.value = null
  if (!connection) {
    Object.assign(form, {
      name: '',
      kind: 'sqlite',
      host: '127.0.0.1',
      port: null,
      username: '',
      password: '',
      database: '',
      sqlite_path: '',
      charset: 'utf8mb4',
      read_only: false,
    })
    return
  }
  Object.assign(form, {
    name: connection.name || '',
    kind: connection.kind || 'sqlite',
    host: connection.host || '127.0.0.1',
    port: connection.port || DEFAULT_PORTS[connection.kind] || null,
    username: connection.username || '',
    password: '',
    database: connection.database || '',
    sqlite_path: connection.sqlite_path || '',
    charset: connection.options?.charset || 'utf8mb4',
    read_only: Boolean(connection.read_only),
  })
}

watch(visible, (open) => {
  if (open) fillForm(props.connection)
})

watch(
  () => props.connection,
  (connection) => {
    if (visible.value) fillForm(connection)
  },
)

function changeKind(kind) {
  if (form.kind === kind) return
  const previousDefault = DEFAULT_PORTS[form.kind]
  form.kind = kind
  if (!form.port || form.port === previousDefault) {
    form.port = DEFAULT_PORTS[kind] || null
  }
  testResult.value = null
}

function buildPayload() {
  const payload = {
    name: form.name.trim(),
    kind: form.kind,
    host: form.kind === 'sqlite' ? null : form.host?.trim() || '127.0.0.1',
    port: form.kind === 'sqlite' ? null : form.port || DEFAULT_PORTS[form.kind] || null,
    username: form.kind === 'sqlite' ? null : form.username || null,
    database: form.kind === 'sqlite' ? null : form.database || null,
    sqlite_path: form.kind === 'sqlite' ? form.sqlite_path.trim() : null,
    options: form.kind === 'mysql' ? { charset: form.charset } : {},
    read_only: Boolean(form.read_only),
  }
  if (form.password) payload.password = form.password
  return payload
}

function validate() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写连接名称')
    return false
  }
  if (form.kind === 'sqlite' && !form.sqlite_path.trim()) {
    ElMessage.warning('请填写 SQLite 数据库文件路径')
    return false
  }
  if (form.kind !== 'sqlite' && !form.host?.trim()) {
    ElMessage.warning('请填写数据库主机地址')
    return false
  }
  return true
}

async function handleTest() {
  if (!validate()) return
  testing.value = true
  testResult.value = null
  try {
    const payload = buildPayload()
    if (isEdit.value) payload.id = props.connection.id
    testResult.value = await api.testConnection(payload)
  } catch (error) {
    testResult.value = { ok: false, message: error.message }
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  if (!validate()) return
  saving.value = true
  try {
    const payload = buildPayload()
    const saved = isEdit.value
      ? await api.updateConnection(props.connection.id, payload)
      : await api.createConnection(payload)
    ElMessage.success(isEdit.value ? '连接已更新' : '连接已创建')
    visible.value = false
    emit('saved', saved)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    saving.value = false
  }
}

function resetTest() {
  testResult.value = null
}
</script>
