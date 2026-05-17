<script setup lang="ts">
// Phase 7b — router-level wrapper. Layout / behaviour lives in
// ``StageModuleView``; we keep this file so the existing
// ``/preprocess`` route + breadcrumb keeps a stable identity even
// though both stage views now share scaffolding.
import StageModuleView from './StageModuleView.vue'
</script>

<template>
  <StageModuleView stage="preprocess" />
</template>
