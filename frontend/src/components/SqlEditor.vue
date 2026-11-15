<template>
  <div ref="host" class="sql-editor" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { EditorView, keymap, placeholder as placeholderExtension } from '@codemirror/view'
import { Compartment } from '@codemirror/state'
import { MSSQL, MySQL, PLSQL, PostgreSQL, SQLite, StandardSQL, sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'

const props = defineProps({
  modelValue: { type: String, default: '' },
  dialect: { type: String, default: 'sqlite' },
  schema: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: '-- 输入 SQL，按 ⌘ / Ctrl + Enter 执行' },
})

const emit = defineEmits(['update:modelValue', 'run'])

const host = ref(null)
const languageCompartment = new Compartment()
let view = null

const DIALECTS = {
  mysql: MySQL,
  postgresql: PostgreSQL,
  sqlite: SQLite,
  mssql: MSSQL,
  oracle: PLSQL,
}

function languageExtension() {
  return sql({
    dialect: DIALECTS[props.dialect] || StandardSQL,
    schema: props.schema || {},
    upperCaseKeywords: true,
  })
}

onMounted(() => {
  view = new EditorView({
    parent: host.value,
    doc: props.modelValue || '',
    extensions: [
      keymap.of([
        {
          key: 'Mod-Enter',
          run: () => {
            emit('run')
            return true
          },
        },
      ]),
      basicSetup,
      oneDark,
      languageCompartment.of(languageExtension()),
      placeholderExtension(props.placeholder),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
      }),
      EditorView.theme({
        '&': { height: '100%', fontSize: '13px' },
        '.cm-scroller': {
          fontFamily:
            "'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace",
          lineHeight: '1.65',
        },
        '.cm-content': { padding: '12px 0' },
        '.cm-gutters': { backgroundColor: '#0d1526', border: 'none' },
        '.cm-activeLineGutter': { backgroundColor: '#172033' },
      }),
    ],
  })
})

watch(
  () => props.modelValue,
  (value) => {
    if (!view) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({
        changes: { from: 0, to: current.length, insert: value || '' },
      })
    }
  },
)

watch(
  () => [props.dialect, props.schema],
  () => {
    if (!view) return
    view.dispatch({
      effects: languageCompartment.reconfigure(languageExtension()),
    })
  },
)

onBeforeUnmount(() => {
  if (view) {
    view.destroy()
    view = null
  }
})
</script>
