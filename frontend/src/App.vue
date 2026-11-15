<template>
  <div class="app-shell">
    <aside class="rail">
      <div class="rail-brand">
        <span class="brand-mark">
          <svg viewBox="0 0 64 64" width="34" height="34" aria-hidden="true">
            <rect width="64" height="64" rx="15" fill="url(#brandGradient)" />
            <ellipse cx="32" cy="20" rx="17" ry="7" fill="#fff" />
            <path
              d="M15 20v24c0 3.9 7.6 7 17 7s17-3.1 17-7V20c0 3.9-7.6 7-17 7s-17-3.1-17-7z"
              fill="#fff"
              opacity=".9"
            />
            <defs>
              <linearGradient id="brandGradient" x1="0" y1="0" x2="64" y2="64">
                <stop stop-color="#22c55e" />
                <stop offset="1" stop-color="#0d9488" />
              </linearGradient>
            </defs>
          </svg>
        </span>
        <div class="brand-copy">
          <span class="brand-name">SQL Station</span>
          <span class="brand-sub">数据库工作台</span>
        </div>
      </div>

      <button type="button" class="new-conn-btn" @click="openCreateConnection">
        <el-icon><Plus /></el-icon>
        <span>新建连接</span>
      </button>

      <div class="rail-label">
        <span>连接</span>
        <em>{{ connections.length }}</em>
      </div>

      <div class="rail-connections">
        <div v-if="loadingConnections" class="rail-skeleton">
          <div v-for="index in 3" :key="index" class="skeleton-conn" />
        </div>
        <div v-else-if="!connections.length" class="rail-empty">
          <el-icon><Connection /></el-icon>
          <span>还没有数据库连接</span>
        </div>
        <div
          v-for="connection in connections"
          :key="connection.id"
          :class="['conn-item', { active: connection.id === activeId }]"
          @click="selectConnection(connection)"
        >
          <span class="conn-badge" :style="{ background: kindColor(connection.kind) }">
            {{ kindMeta(connection.kind).short }}
          </span>
          <div class="conn-copy">
            <span class="conn-name" :title="connection.name">{{ connection.name }}</span>
            <span class="conn-sub" :title="connectionSubtitle(connection)">
              {{ kindLabel(connection.kind) }} · {{ connectionSubtitle(connection) }}
            </span>
          </div>
          <el-dropdown trigger="click" @command="(command) => handleConnectionCommand(command, connection)">
            <button type="button" class="conn-more" title="更多操作" @click.stop>
              <el-icon><MoreFilled /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit" :icon="EditPen">编辑连接</el-dropdown-item>
                <el-dropdown-item command="test" :icon="Connection">测试连接</el-dropdown-item>
                <el-dropdown-item command="delete" :icon="Delete" divided>删除连接</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div class="rail-footer">
        <span class="footer-status"><i /> 本地运行</span>
        <span class="footer-version">v1.0</span>
      </div>
    </aside>

    <TableSidebar
      v-if="activeConnection"
      :connection="activeConnection"
      :catalogs="catalogs"
      :database="database"
      :schema="schema"
      :tables="tables"
      :views="views"
      :loading="loadingTables"
      @select="openTable"
      @refresh="loadTables"
      @query="openQuery"
      @edit="editConnection(activeConnection)"
      @update:database="onDatabaseChange"
      @update:schema="onSchemaChange"
    />

    <main class="workspace">
      <template v-if="activeConnection">
        <div class="tabbar">
          <div class="tabbar-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              :class="['tab-item', { active: tab.key === activeTabKey }]"
              @click="activeTabKey = tab.key"
            >
              <el-icon class="tab-icon">
                <EditPen v-if="tab.type === 'query'" />
                <Grid v-else />
              </el-icon>
              <span class="tab-label" :title="tab.title">{{ tab.title }}</span>
              <span class="tab-close" @click.stop="closeTab(tab.key)">
                <el-icon><Close /></el-icon>
              </span>
            </button>
            <button type="button" class="tab-add" title="新建 SQL 查询（⌘/Ctrl + K）" @click="openQuery">
              <el-icon><Plus /></el-icon>
              <span class="tab-add-label">SQL 查询</span>
            </button>
          </div>
          <div class="tabbar-context">
            <span v-if="database" class="context-chip">{{ database }}</span>
            <span v-if="schema" class="context-chip subtle">{{ schema }}</span>
            <span v-if="activeConnection.read_only" class="readonly-pill">
              <el-icon><Lock /></el-icon>只读
            </span>
          </div>
        </div>

        <div class="workspace-body">
          <KeepAlive :max="24">
            <component
              :is="paneComponent"
              :key="paneKey"
              v-bind="paneProps"
              @query="openQuery"
              @select="openTable"
              @edit="editConnection(activeConnection)"
              @refresh="loadTables"
            />
          </KeepAlive>
        </div>
      </template>

      <div v-else class="welcome">
        <div v-if="loadingConnections" class="welcome-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在加载工作台…</span>
        </div>
        <div v-else class="welcome-card">
          <div class="welcome-logo">
            <svg viewBox="0 0 64 64" width="60" height="60" aria-hidden="true">
              <rect width="64" height="64" rx="17" fill="url(#welcomeGradient)" />
              <ellipse cx="32" cy="20" rx="17" ry="7" fill="#fff" />
              <path
                d="M15 20v24c0 3.9 7.6 7 17 7s17-3.1 17-7V20c0 3.9-7.6 7-17 7s-17-3.1-17-7z"
                fill="#fff"
                opacity=".9"
              />
              <defs>
                <linearGradient id="welcomeGradient" x1="0" y1="0" x2="64" y2="64">
                  <stop stop-color="#22c55e" />
                  <stop offset="1" stop-color="#0d9488" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div class="welcome-kicker">MULTI-DATABASE SQL WORKBENCH</div>
          <h1>连接你的数据库</h1>
          <p class="welcome-lead">
            一个简洁的 SQL 管理工作台。连接 SQLite、MySQL、PostgreSQL、SQL Server 或 Oracle，
            在一个界面中浏览数据、查看表结构并执行 SQL。
          </p>
          <div class="welcome-actions">
            <el-button type="primary" size="large" :icon="Plus" @click="openCreateConnection">
              新建数据库连接
            </el-button>
          </div>
          <div class="welcome-drivers">
            <span v-for="option in DRIVER_OPTIONS" :key="option.value" class="welcome-driver">
              <i :style="{ background: kindColor(option.value) }" />
              {{ option.label }}
            </span>
          </div>
          <div class="welcome-features">
            <div class="welcome-feature">
              <span class="feature-icon"><el-icon><Grid /></el-icon></span>
              <h3>数据浏览</h3>
              <p>分页浏览、条件筛选、排序与行级增删改</p>
            </div>
            <div class="welcome-feature">
              <span class="feature-icon"><el-icon><EditPen /></el-icon></span>
              <h3>SQL 编辑器</h3>
              <p>语法高亮、表字段补全、多语句执行与结果导出</p>
            </div>
            <div class="welcome-feature">
              <span class="feature-icon"><el-icon><Lock /></el-icon></span>
              <h3>安全可靠</h3>
              <p>密码加密存储，支持连接只读保护</p>
            </div>
          </div>
          <p class="welcome-hint">
            数据库凭据仅保存在本机后端 <code>data</code> 目录，不会上传到任何第三方服务。
          </p>
        </div>
      </div>
    </main>

    <ConnectionDialog
      v-model="connectionDialogVisible"
      :connection="editingConnection"
      @saved="onConnectionSaved"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  Close,
  Connection,
  Delete,
  EditPen,
  Grid,
  Loading,
  Lock,
  MoreFilled,
  Plus,
} from '@element-plus/icons-vue'
import { api } from './api'
import {
  DRIVER_OPTIONS,
  connectionSubtitle,
  kindColor,
  kindLabel,
  kindMeta,
} from './utils'
import ConnectionDialog from './components/ConnectionDialog.vue'
import DashboardPane from './components/DashboardPane.vue'
import QueryPane from './components/QueryPane.vue'
import TablePane from './components/TablePane.vue'
import TableSidebar from './components/TableSidebar.vue'

const connections = ref([])
const activeId = ref(null)
const catalogs = ref({ databases: [], schemas: [], current_database: null, namespace: 'schema' })
const database = ref(null)
const schema = ref(null)
const tables = ref([])
const views = ref([])
const loadingTables = ref(false)
const loadingConnections = ref(true)

const tabs = ref([])
const activeTabKey = ref(null)
let querySequence = 0

const connectionDialogVisible = ref(false)
const editingConnection = ref(null)

const activeConnection = computed(
  () => connections.value.find((connection) => connection.id === activeId.value) || null,
)

const activeTab = computed(
  () => tabs.value.find((tab) => tab.key === activeTabKey.value) || null,
)

const paneComponent = computed(() => {
  if (!activeTab.value) return DashboardPane
  return activeTab.value.type === 'query' ? QueryPane : TablePane
})

const paneKey = computed(() =>
  activeTab.value ? activeTab.value.key : `dashboard:${activeId.value}`,
)

const paneProps = computed(() => {
  if (!activeConnection.value) return {}
  if (!activeTab.value) {
    return {
      connection: activeConnection.value,
      catalogs: catalogs.value,
      database: database.value,
      schema: schema.value,
      tables: tables.value,
      views: views.value,
    }
  }
  if (activeTab.value.type === 'query') {
    return {
      tab: activeTab.value,
      connection: activeConnection.value,
      catalogs: catalogs.value,
    }
  }
  return { tab: activeTab.value, connection: activeConnection.value }
})

function closeAllTabs() {
  tabs.value = []
  activeTabKey.value = null
}

async function loadConnections() {
  loadingConnections.value = true
  try {
    connections.value = await api.listConnections()
    if (connections.value.length) {
      await selectConnection(connections.value[0])
    }
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loadingConnections.value = false
  }
}

async function selectConnection(connection) {
  if (!connection) return
  if (activeId.value === connection.id) {
    await loadTables()
    return
  }
  activeId.value = connection.id
  closeAllTabs()
  catalogs.value = { databases: [], schemas: [], current_database: null, namespace: 'schema' }
  database.value = null
  schema.value = null
  tables.value = []
  views.value = []
  await loadCatalogs()
}

async function loadCatalogs(requestedDatabase = null) {
  if (!activeConnection.value) return
  loadingTables.value = true
  try {
    const data = await api.catalogs(activeConnection.value.id, requestedDatabase)
    catalogs.value = data

    const databases = data.databases || []
    let nextDatabase = requestedDatabase || data.current_database || databases[0] || null
    if (nextDatabase && databases.length && !databases.includes(nextDatabase)) {
      nextDatabase = databases[0]
    }
    database.value = nextDatabase

    const schemas = data.schemas || []
    if (schemas.length) {
      const preferred =
        activeConnection.value.kind === 'postgresql'
          ? 'public'
          : activeConnection.value.kind === 'mssql'
            ? 'dbo'
            : data.current_database
      schema.value = schemas.includes(preferred) ? preferred : schemas[0]
    } else {
      schema.value = null
    }

    await loadTables()
  } catch (error) {
    tables.value = []
    views.value = []
    ElMessage.error(error.message)
  } finally {
    loadingTables.value = false
  }
}

async function loadTables() {
  if (!activeConnection.value) return
  loadingTables.value = true
  try {
    const data = await api.tables(activeConnection.value.id, database.value, schema.value)
    tables.value = data.tables || []
    views.value = data.views || []
  } catch (error) {
    tables.value = []
    views.value = []
    ElMessage.error(error.message)
  } finally {
    loadingTables.value = false
  }
}

async function onDatabaseChange(value) {
  database.value = value
  await loadCatalogs(value)
}

async function onSchemaChange(value) {
  schema.value = value
  await loadTables()
}

function openQuery() {
  if (!activeConnection.value) {
    openCreateConnection()
    return
  }
  querySequence += 1
  const key = `query:${activeConnection.value.id}:${Date.now()}:${querySequence}`
  tabs.value.push({
    key,
    type: 'query',
    title: querySequence === 1 ? 'SQL 查询' : `SQL 查询 ${querySequence}`,
    connectionId: activeConnection.value.id,
    database: database.value,
    schema: schema.value,
  })
  activeTabKey.value = key
}

function openTable(table) {
  if (!activeConnection.value || !table) return
  const key = `table:${activeConnection.value.id}:${database.value || ''}:${schema.value || ''}:${table.name}`
  const existing = tabs.value.find((tab) => tab.key === key)
  if (existing) {
    activeTabKey.value = key
    return
  }
  tabs.value.push({
    key,
    type: 'table',
    title: table.name,
    connectionId: activeConnection.value.id,
    database: database.value,
    schema: schema.value,
    table: table.name,
    objType: table.type || 'table',
  })
  activeTabKey.value = key
}

function closeTab(key) {
  const index = tabs.value.findIndex((tab) => tab.key === key)
  if (index === -1) return
  tabs.value.splice(index, 1)
  if (activeTabKey.value === key) {
    const next = tabs.value[index] || tabs.value[index - 1] || null
    activeTabKey.value = next?.key || null
  }
}

function openCreateConnection() {
  editingConnection.value = null
  connectionDialogVisible.value = true
}

function editConnection(connection) {
  if (!connection) {
    openCreateConnection()
    return
  }
  editingConnection.value = connection
  connectionDialogVisible.value = true
}

async function onConnectionSaved(saved) {
  const index = connections.value.findIndex((connection) => connection.id === saved.id)
  if (index === -1) {
    connections.value.push(saved)
    await selectConnection(saved)
    return
  }

  const previous = connections.value[index]
  const contextChanged =
    previous.kind !== saved.kind ||
    previous.host !== saved.host ||
    previous.port !== saved.port ||
    previous.database !== saved.database ||
    previous.sqlite_path !== saved.sqlite_path

  connections.value[index] = saved
  if (activeId.value === saved.id) {
    if (contextChanged) closeAllTabs()
    await loadCatalogs(contextChanged ? null : database.value)
  }
}

async function testSavedConnection(connection) {
  const notification = ElNotification({
    title: '正在测试连接',
    message: connection.name,
    type: 'info',
    duration: 0,
  })
  try {
    const result = await api.testConnection({
      id: connection.id,
      name: connection.name,
      kind: connection.kind,
      host: connection.host,
      port: connection.port,
      username: connection.username,
      database: connection.database,
      sqlite_path: connection.sqlite_path,
      options: connection.options,
      read_only: connection.read_only,
    })
    notification.close()
    ElNotification({
      title: result.ok ? '连接正常' : '连接失败',
      message: result.message,
      type: result.ok ? 'success' : 'error',
      duration: result.ok ? 3500 : 7000,
    })
  } catch (error) {
    notification.close()
    ElNotification({ title: '连接失败', message: error.message, type: 'error', duration: 7000 })
  }
}

async function deleteConnection(connection) {
  try {
    await ElMessageBox.confirm(
      `确定删除连接「${connection.name}」吗？只会删除保存的连接配置，不会影响数据库中的数据。`,
      '删除连接',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    await api.deleteConnection(connection.id)
    const index = connections.value.findIndex((item) => item.id === connection.id)
    if (index >= 0) connections.value.splice(index, 1)
    ElMessage.success('连接已删除')

    if (activeId.value === connection.id) {
      activeId.value = null
      closeAllTabs()
      catalogs.value = { databases: [], schemas: [], current_database: null, namespace: 'schema' }
      database.value = null
      schema.value = null
      tables.value = []
      views.value = []
      if (connections.value.length) await selectConnection(connections.value[0])
    }
  } catch (error) {
    ElMessage.error(error.message)
  }
}

function handleConnectionCommand(command, connection) {
  if (command === 'edit') editConnection(connection)
  else if (command === 'test') testSavedConnection(connection)
  else if (command === 'delete') deleteConnection(connection)
}

function onGlobalKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    openQuery()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  loadConnections()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})
</script>
