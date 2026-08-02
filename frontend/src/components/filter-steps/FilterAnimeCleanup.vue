<script setup lang="ts">
import BaseSelect from '@/components/forms/BaseSelect.vue'
import FilterNumberField from './FilterNumberField.vue'
import {
  ANIME_CLEANUP_FIELD_CONSTRAINTS,
  ANIME_CLEANUP_PROFILE_OPTIONS,
  animeCleanupParamsForProfile,
  type AnimeCleanupProfile,
} from '@/services/filters/anime-cleanup'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import { APPLICATION_DEFAULTS } from '@/types/protocol'
import type { FilterStep } from '@/types/protocol'

type AnimeCleanupFilterStep = Extract<FilterStep, { kind: 'anime_cleanup' }>

const modelValue = defineModel<AnimeCleanupFilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
const defaultParams = animeCleanupParamsForProfile(APPLICATION_DEFAULTS.filters.animeCleanup.defaultProfile)

function setProfile(profile: AnimeCleanupProfile): void {
  patch((params) => Object.assign(params, animeCleanupParamsForProfile(profile)))
}
</script>

<template>
  <div class="field-grid field-grid-3">
    <BaseSelect
      :model-value="modelValue.params.profile ?? defaultParams.profile"
      label="预设"
      :options="ANIME_CLEANUP_PROFILE_OPTIONS"
      @update:model-value="setProfile($event)"
    />
    <FilterNumberField
      :model-value="Number(modelValue.params.denoise ?? defaultParams.denoise)"
      label="降噪"
      :min="ANIME_CLEANUP_FIELD_CONSTRAINTS.denoise.minimum"
      :max="ANIME_CLEANUP_FIELD_CONSTRAINTS.denoise.maximum"
      @update:model-value="patch((params) => (params.denoise = $event))"
    />
    <FilterNumberField
      :model-value="Number(modelValue.params.edgeBoost ?? defaultParams.edgeBoost)"
      label="边缘增强"
      :min="ANIME_CLEANUP_FIELD_CONSTRAINTS.edgeBoost.minimum"
      :max="ANIME_CLEANUP_FIELD_CONSTRAINTS.edgeBoost.maximum"
      @update:model-value="patch((params) => (params.edgeBoost = $event))"
    />
  </div>
</template>
