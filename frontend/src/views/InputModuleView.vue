<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatNumber, resolvePrimaryMode } from '@/lib/task-mapper'
import { WORKFLOW_LABELS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { CapabilityOptionSpec, CapabilityValue, MediaItem } from '@/types'

const store = useWorkbenchStore()
const dragActive = ref(false)

const importedCount = computed(() => store.mediaItems.length)
const inspectedCount = computed(() => store.mediaItems.filter((item) => item.info).length)
const decoderOptions = computed(() => store.currentDecoderProfile?.options ?? [])
const inputOperationIssue = computed(() =>
  store.operationIssue?.scope === 'input' ? store.operationIssue.error : null,
)

const inputStats = computed(() => [
  { label: '已导入', value: `${importedCount.value}` },
  { label: '已勾选', value: `${store.selectedIds.length}` },
  { label: '已读信息', value: `${inspectedCount.value}` },
  { label: '激活文件', value: store.activeItem?.displayName ?? '--' },
])

function getPipelineSummary(item: MediaItem): string {
  const labels = [
    item.workflowConfig.interpolation.enabled ? '补帧' : null,
    item.workflowConfig.superResolution.enabled ? '超分' : null,
    item.workflowConfig.anime.enabled ? '动漫' : null,
  ].filter(Boolean)
  return labels.length > 0 ? labels.join(' / ') : WORKFLOW_LABELS[resolvePrimaryMode(item)]
}

function getDecoderSummary(item: MediaItem): string {
  if (item.decodeConfig.mode === 'software') {
    return 'software'
  }
  return `${item.decodeConfig.decoder} / ${item.decodeConfig.hwaccel}`
}

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

async function reinspectSelection(): Promise<void> {
  const ids = store.selectedIds.length > 0 ? store.selectedIds : store.activeItem ? [store.activeItem.id] : []
  await store.inspectItems(ids)
}

async function handleDrop(event: DragEvent): Promise<void> {
  dragActive.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  const paths = files
    .map((file) => (file as File & { path?: string }).path)
    .filter((path): path is string => Boolean(path))

  if (paths.length > 0) {
    await store.addMediaPaths(paths)
  }
}

function handleDragOver(event: DragEvent): void {
  event.preventDefault()
  dragActive.value = true
}

function handleDragLeave(): void {
  dragActive.value = false
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>批量导入</h2>
          <p class="panel-caption">导入后会自动读取素材信息。复选框用于批量套用设置，激活行用于显示当前表单。</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" @click="store.selectAllMedia(!store.allSelected)">
            {{ store.allSelected ? '取消全选' : '全选全部' }}
          </button>
          <button class="ghost-button" :disabled="store.mediaItems.length === 0" @click="reinspectSelection()">
            重新读取
          </button>
          <button class="primary-button" @click="store.pickInputs()">批量导入</button>
        </div>
      </div>

      <div
        class="dropzone"
        :class="{ active: dragActive }"
        @drop.prevent="handleDrop"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
      >
        <strong>拖放视频到这里，或使用“批量导入”按钮</strong>
        <p>支持多文件导入，导入后自动探测分辨率、帧率、音频与视频编码。</p>
      </div>

      <div v-if="inputOperationIssue" class="info-banner info-banner-danger">
        <strong>批量导入失败</strong>
        <p>{{ inputOperationIssue.message }}</p>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in inputStats" :key="item.label" class="stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>素材列表</h2>
          <p class="panel-caption">点击行切换激活文件；修改下方表单时，会同步到激活文件和所有已勾选文件。</p>
        </div>
      </div>

      <div v-if="store.mediaItems.length === 0" class="empty-state">
        <strong>还没有素材</strong>
        <p>前往上方批量导入后，这里会显示每个文件的元数据、流程摘要和任务状态。</p>
      </div>

      <div v-else class="table-wrap">
        <table class="media-table">
          <thead>
            <tr>
              <th class="checkbox-col">选</th>
              <th>文件</th>
              <th>分辨率</th>
              <th>帧率</th>
              <th>编码</th>
              <th>解码</th>
              <th>流程</th>
              <th>状态</th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in store.mediaItems"
              :key="item.id"
              class="media-row"
              :class="{ active: item.id === store.activeItemId }"
              @click="store.setActiveItem(item.id)"
            >
              <td @click.stop>
                <input
                  :checked="item.selected"
                  type="checkbox"
                  @change="store.setItemSelected(item.id, ($event.target as HTMLInputElement).checked)"
                />
              </td>
              <td>
                <div class="table-primary">{{ item.displayName }}</div>
                <div class="table-secondary path-text">{{ item.inputPath }}</div>
              </td>
              <td>{{ item.info ? `${item.info.width}×${item.info.height}` : '--' }}</td>
              <td>{{ item.info ? `${formatNumber(item.info.fps)} FPS` : '--' }}</td>
              <td>{{ item.info?.video_codec || '--' }}</td>
              <td>{{ getDecoderSummary(item) }}</td>
              <td>{{ getPipelineSummary(item) }}</td>
              <td>
                <span class="inline-status" :data-state="item.taskState.status">{{ item.taskState.status }}</span>
              </td>
              <td @click.stop>
                <button class="table-action" :disabled="store.batch.isRunning" @click="store.removeMediaItem(item.id)">
                  移除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>解码设置</h2>
          <p class="panel-caption">选项完全来自启动时的 FFmpeg 探测结果，当前修改会应用到激活文件与所有勾选文件。</p>
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
