<script setup lang="ts">
// 基础字段壳:统一 label / hint / 错误提示的视觉。
// 由 BaseNumber/BaseSelect/BaseToggle 内部复用,也可单独包裹自定义控件。
// 不接管 v-model,仅负责布局。

defineProps<{
  label: string
  /** 当前字段附加的提示文案(可选),会显示在控件下方。 */
  hint?: string
  /** 错误提示(可选);存在则覆盖 hint 并以告警色显示。 */
  error?: string | null
  /** 是否占两列:对应 `.field-span-2` 类,放在 `.field-grid-2/3` 内生效。 */
  spanTwo?: boolean
  /** 是否使用 toggle 样式(label 与控件横排)。 */
  toggle?: boolean
}>()
</script>

<template>
  <label
    class="field"
    :class="{
      'field-span-2': spanTwo,
      'toggle-field': toggle,
    }"
  >
    <span>{{ label }}</span>
    <slot />
    <small v-if="error" class="field-error" role="alert">{{ error }}</small>
    <small v-else-if="hint" class="field-hint">{{ hint }}</small>
  </label>
</template>

<style scoped>
.field-error {
  color: var(--danger);
  font-size: 11px;
}

.field-hint {
  color: var(--text-muted);
  font-size: 11px;
}
</style>
