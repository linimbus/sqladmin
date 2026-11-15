<template>
  <aside class="table-rail">
    <div class="tr-head">
      <div class="tr-conn">
        <span class="tr-dot" :style="{ background: kindColor(connection.kind) }">
          {{ kindMeta(connection.kind).short }}
        </span>
        <div class="tr-conn-text">
          <div class="tr-conn-name" :title="connection.name">{{ connection.name }}</div>
          <div class="tr-conn-meta" :title="connectionSubtitle(connection)">
            {{ kindLabel(connection.kind) }} · {{ connectionSubtitle(connection) }}
          </div>
        </div>
      </div>
      <div class="tr-head-actions">
        <el-tooltip content="新建 SQL 查询" placement="bottom">
          <button class="icon-btn" @click="$emit('query')">
            <el-icon><EditPen /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="刷新对象列表" placement="bottom">
          <button class="icon-btn" :disabled="loading" @click="$emit('refresh')">
            <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="连接设置" placement="bottom">
          <button class="icon-btn" @click="$emit('edit')">
            <el-icon><Setting /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>

    <div v-if="showDatabase || showSchema" class="tr-filters">
      <el-select
        v-if="showDatabase"
        :model-value="database"
        size="small"
        placeholder="选择数据库"
        class="tr-select"
        filterable
        @update:model-value="$emit('update:database', $event)"
      >
        <el-option v-for="name in catalogs.databases || []" :key="name" :label="name" :value="name" />
      </el-select>
      <el-select
        v-if="showSchema"
        :model-value="schema"
        size="small"
        placeholder="选择 Schema"
        class="tr-select"
        filterable
        @update:model-value="$emit('update:schema', $event)"
      >
        <el-option v-for="name in catalogs.schemas || []" :key="name" :label="name" :value="name" />
      </el-select>
    </div>

    <div class="tr-search">
      <el-input
        v-model="search"
        size="small"
        clearable
        placeholder="搜索表 / 视图"
        :prefix-icon="Search"
      />
    </div>

    <div class="tr-scroll">
      <template v-if="loading && !tables.length && !views.length">
        <div class="tr-skeleton">
          <div v-for="index in 7" :key="index" class="skeleton-line" />
        </div>
      </template>
      <template v-else>
        <div class="tr-group">
          <span>表</span>
          <em>{{ filteredTables.length }}</em>
        </div>
        <button
          v-for="table in filteredTables"
          :key="`t-${table.name}`"
          class="obj-item"
          :title="table.comment ? `${table.name} — ${table.comment}` : table.name"
          @click="$emit('select', table)"
        >
          <span class="obj-icon table"><el-icon><Grid /></el-icon></span>
          <span class="obj-name">{{ table.name }}</span>
          <span v-if="table.row_estimate !== null && table.row_estimate !== undefined" class="obj-rows">
            {{ formatNumber(table.row_estimate) }}
          </span>
        </button>
        <div v-if="!filteredTables.length" class="tr-empty">没有匹配的表</div>

        <div v-if="filteredViews.length" class="tr-group views">
          <span>视图</span>
          <em>{{ filteredViews.length }}</em>
        </div>
        <button
          v-for="view in filteredViews"
          :key="`v-${view.name}`"
          class="obj-item"
          :title="view.name"
          @click="$emit('select', view)"
        >
          <span class="obj-icon view"><el-icon><View /></el-icon></span>
          <span class="obj-name">{{ view.name }}</span>
          <span class="obj-tag">VIEW</span>
        </button>
      </template>
    </div>

    <div class="tr-bottom">
      <button type="button" class="new-query-btn" @click="$emit('query')">
        <el-icon><Plus /></el-icon>
        <span>新建 SQL 查询</span>
        <kbd>⌘ K</kbd>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { EditPen, Grid, Plus, Refresh, Search, Setting, View } from '@element-plus/icons-vue'
import {
  connectionSubtitle,
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
  loading: { type: Boolean, default: false },
})

defineEmits(['select', 'refresh', 'query', 'edit', 'update:database', 'update:schema'])

const search = ref('')

const showDatabase = computed(
  () => props.connection.kind === 'mysql' || props.connection.kind === 'mssql',
)
const showSchema = computed(
  () => props.connection.kind !== 'sqlite' && (props.catalogs.schemas || []).length > 0,
)

function matches(name) {
  const keyword = search.value.trim().toLowerCase()
  return !keyword || name.toLowerCase().includes(keyword)
}

const filteredTables = computed(() => props.tables.filter((table) => matches(table.name)))
const filteredViews = computed(() => props.views.filter((view) => matches(view.name)))
</script>
