<script setup lang="ts">
// 统一的"操作问题"内联横幅。
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
}>()
</script>

<template>
  <div
    v-if="issue"
    class="info-banner info-banner-danger"
    role="alert"
  >
    <strong>{{ title }}</strong>
    <p>{{ issue.message }}</p>
    <slot name="details" :issue="issue" />
  </div>
</template>
