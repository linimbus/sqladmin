<template>
  <div ref="wrapper" class="data-grid">
    <el-table
      :data="rowObjects"
      :height="tableHeight"
      size="small"
      border
      stripe
      highlight-current-row
      :row-key="rowKey"
      v-loading="loading"
      @sort-change="onSortChange"
    >
      <el-table-column
        v-if="showIndex"
        type="index"
        label="#"
        width="58"
        fixed="left"
        align="right"
        :index="indexMethod"
      />
      <el-table-column
        v-for="(column, index) in columns"
        :key="`${index}-${column.name}`"
        :prop="`c${index}`"
        :label="column.name"
        :min-width="columnWidth(column)"
        :sortable="sortable ? 'custom' : false"
        show-overflow-tooltip
      >
        <template #header>
          <div class="grid-header">
            <span class="grid-col-name" :title="column.name">{{ column.name }}</span>
            <span v-if="column.type" class="grid-col-type">{{ shortType(column.type) }}</span>
          </div>
        </template>
        <template #default="{ row }">
          <span v-if="row[`c${index}`] === null" class="cell-null">NULL</span>
          <span v-else-if="typeof row[`c${index}`] === 'object'" class="cell-json">
            {{ displayCell(row[`c${index}`]) }}
          </span>
          <span v-else class="cell-value">{{ row[`c${index}`] }}</span>
        </template>
      </el-table-column>

      <el-table-column v-if="editable" label="操作" width="112" fixed="right" align="center">
        <template #default="{ $index }">
          <el-button link type="primary" size="small" @click="$emit('edit', rows[$index])">
            编辑
          </el-button>
          <el-button link type="danger" size="small" @click="$emit('delete', rows[$index])">
            删除
          </el-button>
        </template>
      </el-table-column>

      <template #empty>
        <div class="grid-empty">
          <el-icon><Files /></el-icon>
          <span>{{ emptyText }}</span>
        </div>
      </template>
    </el-table>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Files } from '@element-plus/icons-vue'
import { columnWidth, displayCell, shortType } from '../utils'

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  editable: { type: Boolean, default: false },
  sortable: { type: Boolean, default: true },
  showIndex: { type: Boolean, default: true },
  startIndex: { type: Number, default: 0 },
  emptyText: { type: String, default: '暂无数据' },
})

const emit = defineEmits(['sort-change', 'edit', 'delete'])

const wrapper = ref(null)
const tableHeight = ref(360)
let observer = null

onMounted(() => {
  if (!wrapper.value) return
  const update = () => {
    tableHeight.value = Math.max(120, wrapper.value?.clientHeight || 360)
  }
  update()
  observer = new ResizeObserver(update)
  observer.observe(wrapper.value)
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})

const rowObjects = computed(() =>
  props.rows.map((row) => {
    const output = {}
    row.forEach((value, index) => {
      output[`c${index}`] = value
    })
    return output
  }),
)

function rowKey(row, index) {
  return index
}

function indexMethod(index) {
  return props.startIndex + index + 1
}

function onSortChange({ prop, order }) {
  if (!prop) return
  const index = Number(String(prop).replace('c', ''))
  const column = props.columns[index]
  if (!column) return
  emit('sort-change', {
    name: column.name,
    order: order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : null,
  })
}
</script>
