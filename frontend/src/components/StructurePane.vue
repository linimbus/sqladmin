<template>
  <div class="structure-pane" v-loading="loading">
    <template v-if="detail">
      <div class="structure-summary">
        <div class="summary-item">
          <span class="summary-label">字段</span>
          <span class="summary-value">{{ detail.columns.length }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">主键</span>
          <span class="summary-value">
            <template v-if="detail.primary_key.length">
              <el-tag v-for="name in detail.primary_key" :key="name" size="small" effect="plain">
                {{ name }}
              </el-tag>
            </template>
            <span v-else class="muted">无</span>
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">索引</span>
          <span class="summary-value">{{ detail.indexes.length }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">外键</span>
          <span class="summary-value">{{ detail.foreign_keys.length }}</span>
        </div>
        <el-tag class="summary-type" effect="plain" :type="detail.type === 'view' ? 'warning' : 'info'">
          {{ detail.type === 'view' ? 'VIEW' : 'TABLE' }}
        </el-tag>
      </div>

      <section class="structure-section">
        <header>
          <h4>字段结构</h4>
          <span>{{ detail.schema ? `${detail.schema}.` : '' }}{{ detail.name }}</span>
        </header>
        <el-table :data="detail.columns" size="small" border class="structure-table">
          <el-table-column prop="name" label="字段" min-width="180">
            <template #default="{ row }">
              <span class="col-name">
                <el-icon v-if="row.primary_key" class="pk-icon"><Key /></el-icon>
                {{ row.name }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" min-width="150" show-overflow-tooltip />
          <el-table-column label="可空" width="76" align="center">
            <template #default="{ row }">
              <span :class="row.nullable ? 'yes' : 'no'">{{ row.nullable ? '是' : '否' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="默认值" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <code v-if="row.default !== null && row.default !== undefined" class="default-value">
                {{ row.default }}
              </code>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="属性" min-width="110">
            <template #default="{ row }">
              <el-tag v-if="row.autoincrement" size="small" type="success" effect="plain">AUTO</el-tag>
              <el-tag v-if="row.computed" size="small" type="info" effect="plain">GENERATED</el-tag>
              <el-tag v-if="row.primary_key" size="small" type="warning" effect="plain">PK</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="注释" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span :class="{ muted: !row.comment }">{{ row.comment || '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section v-if="detail.indexes.length" class="structure-section">
        <header><h4>索引</h4><span>{{ detail.indexes.length }} 个</span></header>
        <el-table :data="detail.indexes" size="small" border>
          <el-table-column prop="name" label="索引名" min-width="200" show-overflow-tooltip />
          <el-table-column label="字段" min-width="220">
            <template #default="{ row }">
              <el-tag
                v-for="column in row.columns"
                :key="column"
                size="small"
                effect="plain"
                class="column-chip"
              >
                {{ column }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="唯一" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.unique" size="small" type="success" effect="plain">UNIQUE</el-tag>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section v-if="detail.foreign_keys.length" class="structure-section">
        <header><h4>外键</h4><span>{{ detail.foreign_keys.length }} 个</span></header>
        <el-table :data="detail.foreign_keys" size="small" border>
          <el-table-column prop="name" label="约束名" min-width="180" show-overflow-tooltip />
          <el-table-column label="字段" min-width="180">
            <template #default="{ row }">{{ row.columns.join(', ') }}</template>
          </el-table-column>
          <el-table-column label="引用" min-width="240">
            <template #default="{ row }">
              <span class="fk-target">
                {{ row.referred_table }}({{ (row.referred_columns || []).join(', ') }})
              </span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="structure-section">
        <header>
          <h4>DDL</h4>
          <el-button link type="primary" :icon="CopyDocument" @click="copyDdl">复制</el-button>
        </header>
        <pre class="ddl-block">{{ detail.ddl || '当前数据库暂不支持生成 DDL' }}</pre>
      </section>
    </template>

    <div v-else-if="!loading" class="structure-empty">暂无结构信息</div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { CopyDocument, Key } from '@element-plus/icons-vue'
import { copyToClipboard } from '../utils'

const props = defineProps({
  detail: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

async function copyDdl() {
  if (!props.detail?.ddl) return
  try {
    await copyToClipboard(props.detail.ddl)
    ElMessage.success('DDL 已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>
