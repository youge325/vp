<script setup lang="ts">
import BaseSelect from '@/components/forms/BaseSelect.vue'
import FilterNumberField from './FilterNumberField.vue'
import {
  ANIME_CLEANUP_PROFILE_OPTIONS,
  animeCleanupParamsForProfile,
  type AnimeCleanupProfile,
} from '@/services/filters/anime-cleanup'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)

function setProfile(profile: AnimeCleanupProfile): void {
  patch((params) => Object.assign(params, animeCleanupParamsForProfile(profile)))
}
</script>

<template>
  <div class="field-grid field-grid-3">
    <BaseSelect
      :model-value="String(modelValue.params.profile ?? 'clean-lines')"
      label="预设"
      :options="ANIME_CLEANUP_PROFILE_OPTIONS"
      @update:model-value="setProfile($event as AnimeCleanupProfile)"
    />
    <FilterNumberField
      :model-value="Number(modelValue.params.denoise ?? 15)"
      label="降噪"
      :min="0"
      :max="100"
      @update:model-value="patch((params) => (params.denoise = $event))"
    />
    <FilterNumberField
      :model-value="Number(modelValue.params.edgeBoost ?? 30)"
      label="边缘增强"
      :min="0"
      :max="100"
      @update:model-value="patch((params) => (params.edgeBoost = $event))"
    />
  </div>
</template>
