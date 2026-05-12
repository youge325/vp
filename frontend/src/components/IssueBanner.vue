<script setup lang="ts">
// 统一的"操作问题"内联横幅。
// Phase C.3.1 抽出来,替换四个 module view 里重复出现的
//   <div v-if="issue" class="info-banner info-banner-danger">
//     <strong>...</strong>
//     <p>{{ issue.message }}</p>
//   </div>
// 块,把标题文案作为 prop 而不是写死。
// 视图内联保留(而非提升为浮层 toast)是有意的:横幅的位置本身告诉用户
// "哪个操作失败了"——把它挪走会丢失这种上下文。

import type { TaskError } from '@/types/domain/media'

defineProps<{
  /**
   * 要展示的错误对象;``null`` 时整个横幅不渲染。
   */
  issue: TaskError | null
  /**
   * 横幅标题,例如"批量导入失败"。短句,无标点。
   */
  title: string
  /**
   * 严重级别;影响背景色和图标(目前 ``error`` 一种,后续扩展)。
   */
  variant?: 'error' | 'warning'
}>()
</script>

<template>
  <div
    v-if="issue"
    class="info-banner"
    :class="variant === 'warning' ? 'info-banner-warning' : 'info-banner-danger'"
    role="alert"
  >
    <strong>{{ title }}</strong>
    <p>{{ issue.message }}</p>
    <slot name="details" :issue="issue" />
  </div>
</template>
