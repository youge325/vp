<script setup lang="ts">
import {
  ANIME_CLEANUP_PROFILE_OPTIONS,
  animeCleanupParamsForProfile,
  type AnimeCleanupProfile,
} from '@/services/filters/anime-cleanup'
import { createFilterParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const props = defineProps<{ modelValue: FilterStep }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: FilterStep): void }>()
const patch = createFilterParamsPatch(
  () => props.modelValue,
  (value) => emit('update:modelValue', value),
)

function setProfile(profile: AnimeCleanupProfile): void {
  patch((params) => Object.assign(params, animeCleanupParamsForProfile(profile)))
}
</script>

<template>
  <div class="field-grid field-grid-3">
    <label class="field">
      <span>预设</span>
      <select
        :value="String(modelValue.params.profile ?? 'clean-lines')"
        @change="setProfile(($event.target as HTMLSelectElement).value as AnimeCleanupProfile)"
      >
        <option v-for="option in ANIME_CLEANUP_PROFILE_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>降噪</span>
      <input
        :value="Number(modelValue.params.denoise ?? 15)"
        type="number"
        min="0"
        max="100"
        @input="patch((params) => (params.denoise = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>边缘增强</span>
      <input
        :value="Number(modelValue.params.edgeBoost ?? 30)"
        type="number"
        min="0"
        max="100"
        @input="patch((params) => (params.edgeBoost = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
