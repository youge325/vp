<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types'

const store = useWorkbenchStore()

const decoderOptions = computed(() => store.currentDecoderProfile?.options ?? [])

function coerceOptionValue(option: CapabilityOptionSpec, event: Event): CapabilityValue {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  if (option.type === 'boolean') {
    return (target as HTMLInputElement).checked
  }
  if (option.type === 'number') {
    return Number(target.value)
  }
  return target.value
}
</script>

<template>
  <div class="module-stack">
    <section v-if="!store.activeItem" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>解码设置</h2>
          <p class="panel-caption">选项完全来自启动时的 FFmpeg 探测结果，会同步应用到激活文件与所有勾选文件。</p>
        </div>
      </div>

      <div v-if="!store.activeItem" class="empty-state">
        <strong>还没有激活文件</strong>
        <p>请先在输入页导入并激活一个文件，解码页会显示该文件当前的解码方案。</p>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>解码设置</h2>
          <p class="panel-caption">当前修改会应用到激活文件与所有勾选文件，解码器参数来自 FFmpeg 的可用能力探测。</p>
        </div>
        <span class="panel-badge">作用于 {{ store.selectedIds.length || 1 }} 个文件</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>解码方案</span>
          <select
            :value="store.currentDecoderProfile?.name ?? 'software'"
            @change="store.setDecodeProfile(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="profile in store.visibleDecoderProfiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>硬件加速设备</span>
          <input
            :value="store.activeItem.decodeConfig.hwaccelDevice"
            type="text"
            placeholder="留空使用默认设备"
            @input="store.setDecodeHwaccelDevice(($event.target as HTMLInputElement).value)"
          />
        </label>
      </div>

      <div class="chip-row">
        <span class="tag">模式: {{ store.activeItem.decodeConfig.mode }}</span>
        <span class="tag">hwaccel: {{ store.activeItem.decodeConfig.hwaccel || 'software' }}</span>
        <span class="tag">decoder: {{ store.activeItem.decodeConfig.decoder || 'software' }}</span>
      </div>

      <div v-if="decoderOptions.length > 0" class="field-grid field-grid-2">
        <label v-for="option in decoderOptions" :key="option.name" class="field">
          <span>{{ option.label }}</span>

          <label v-if="option.type === 'boolean'" class="toggle-chip">
            <input
              :checked="Boolean(store.getOptionValue(option, store.activeItem.decodeConfig.options))"
              type="checkbox"
              @change="store.setDecodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(store.getOptionValue(option, store.activeItem.decodeConfig.options))"
            @change="store.setDecodeOption(option.name, coerceOptionValue(option, $event))"
          >
            <option
              v-for="choice in option.choices"
              :key="`${option.name}-${choice.value}`"
              :value="String(choice.value)"
            >
              {{ choice.label }}
            </option>
          </select>

          <input
            v-else-if="option.type === 'number'"
            :value="Number(store.getOptionValue(option, store.activeItem.decodeConfig.options))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="store.setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(store.getOptionValue(option, store.activeItem.decodeConfig.options))"
            type="text"
            @input="store.setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
