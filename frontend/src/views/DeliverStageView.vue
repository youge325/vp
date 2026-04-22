<script setup lang="ts">
import { CODEC_OPTIONS, PRESET_OPTIONS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码与输出</h2>
          <p class="panel-caption">聚合输出路径、容器与编码参数</p>
        </div>
        <button class="ghost-button" @click="store.pickOutput()">选择输出</button>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field field-span-2">
          <span>输出文件</span>
          <input v-model="store.output.outputPath" type="text" placeholder="留空则自动生成" />
        </label>

        <label class="field">
          <span>输出目录</span>
          <input v-model="store.output.outputDir" type="text" placeholder="默认输出目录" />
        </label>

        <label class="field">
          <span>临时目录</span>
          <input v-model="store.output.tempDir" type="text" placeholder="默认缓存目录" />
        </label>

        <label class="field toggle-field">
          <span>重封装</span>
          <label class="toggle-chip">
            <input v-model="store.format.remuxOnly" type="checkbox" />
            <span>Only</span>
          </label>
        </label>

        <label class="field toggle-field">
          <span>音频</span>
          <label class="toggle-chip">
            <input v-model="store.format.keepAudio" type="checkbox" />
            <span>Keep</span>
          </label>
        </label>

        <label class="field">
          <span>容器</span>
          <select v-model="store.format.container">
            <option value="mp4">MP4</option>
            <option value="mkv">MKV</option>
            <option value="mov">MOV</option>
            <option value="webm">WEBM</option>
          </select>
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

        <label class="field toggle-field">
          <span>完成后</span>
          <label class="toggle-chip">
            <input v-model="store.output.openOnComplete" type="checkbox" />
            <span>打开目录</span>
          </label>
        </label>
      </div>
    </section>
  </div>
</template>
