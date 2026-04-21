<script setup lang="ts">
import TaskConsole from '@/components/TaskConsole.vue'
import { CODEC_OPTIONS, PRESET_OPTIONS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">输出与执行</p>
          <h2>统一确认参数，然后交给 CLI</h2>
        </div>

        <div class="inline-actions">
          <button class="ghost-button" @click="store.pickOutput()">选择输出文件</button>
          <button
            v-if="store.task.status !== 'running'"
            class="primary-button"
            :disabled="!store.canStartTask"
            @click="store.startTask()"
          >
            开始执行
          </button>
          <button v-else class="danger-button" @click="store.cancelCurrentTask()">取消任务</button>
        </div>
      </div>

      <div class="form-grid">
        <label class="field">
          <span>输出文件</span>
          <input v-model="store.output.outputPath" type="text" placeholder="可选，留空则自动生成" />
        </label>
        <label class="field">
          <span>输出目录</span>
          <input v-model="store.output.outputDir" type="text" placeholder="可选，默认 app 输出目录" />
        </label>
        <label class="field">
          <span>临时目录</span>
          <input v-model="store.output.tempDir" type="text" placeholder="可选，默认 app 缓存目录" />
        </label>
        <label class="field">
          <span>编码器</span>
          <select v-model="store.encode.codec">
            <option v-for="codec in CODEC_OPTIONS" :key="codec" :value="codec">{{ codec }}</option>
          </select>
        </label>
        <label class="field">
          <span>CRF</span>
          <input v-model.number="store.encode.crf" type="number" min="0" max="51" />
        </label>
        <label class="field">
          <span>Preset</span>
          <select v-model="store.encode.preset">
            <option v-for="preset in PRESET_OPTIONS" :key="preset" :value="preset">{{ preset }}</option>
          </select>
        </label>
      </div>

      <div class="switch-row">
        <label class="switch">
          <input v-model="store.workflow.enableInterpolation" type="checkbox" />
          <span>启用补帧</span>
        </label>
        <label class="switch">
          <input
            v-model="store.workflow.enableSuperResolution"
            type="checkbox"
            @change="store.superResolution.enabled = store.workflow.enableSuperResolution"
          />
          <span>启用超分</span>
        </label>
        <label class="switch">
          <input v-model="store.output.openOnComplete" type="checkbox" />
          <span>完成后优先打开输出目录</span>
        </label>
      </div>
    </section>

    <TaskConsole />
  </div>
</template>
