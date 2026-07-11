<script setup lang="ts">
// Phase 7c — Capability-option 渲染抽象。
//
// 替换 DecodeModuleView / EncodeModuleView 模板里完全重复的
// type=boolean/choice/number/fallback 四分支 switch。``option.type`` 决定
// 委托给哪个 ``Base*`` 控件,父组件只需要绑 ``v-model`` + 喂 ``option``。
//
// 把每一种 type 都收敛到对应的 Base* 控件而不是手写 input,可顺手关掉
// 一批散布在视图模板里 ``setX(coerceOptionValue(option, $event))`` 的
// "把 event 当 value 处理"细节;CapabilityValue 类型在 props 出入两端
// 保持一致,caller 不需要知道某种 type 内部用了 string-typed event。

import { computed } from 'vue'

import BaseField from './BaseField.vue'
import BaseNumber from './BaseNumber.vue'
import BaseSelect from './BaseSelect.vue'
import BaseToggle from './BaseToggle.vue'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/protocol'

const props = defineProps<{
  option: CapabilityOptionSpec
  modelValue: CapabilityValue
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: CapabilityValue): void
}>()

// BaseSelect 期待 ``{ value: string, label: string }``;capability choice
// 的 value 在协议上是 ``CapabilityValue``(string | number | boolean),
// 但实际后端探测出的 ffmpeg 选项 99% 是 string。这里统一 ``String(...)``
// 保险一次,emit 时透传 BaseSelect 给出的 string —— 与原视图里
// ``coerceOptionValue`` 的 choice 路径 (``return target.value``) 行为完全
// 一致,不会引入回归。
const choiceOptions = computed(() =>
  props.option.choices.map((choice) => ({
    value: String(choice.value),
    label: choice.label,
  })),
)
</script>

<template>
  <BaseToggle
    v-if="option.type === 'boolean'"
    :model-value="Boolean(modelValue)"
    :label="option.label"
    chip-text="启用"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <BaseSelect
    v-else-if="option.type === 'choice'"
    :model-value="String(modelValue)"
    :label="option.label"
    :options="choiceOptions"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <BaseNumber
    v-else-if="option.type === 'number'"
    :model-value="Number(modelValue)"
    :label="option.label"
    :min="option.min ?? undefined"
    :max="option.max ?? undefined"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <BaseField v-else :label="option.label">
    <input
      :value="String(modelValue)"
      type="text"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </BaseField>
</template>
