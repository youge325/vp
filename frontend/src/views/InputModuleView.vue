<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatNumber, resolvePrimaryMode } from '@/lib/task-mapper'
import { WORKFLOW_LABELS } from '@/lib/workflow'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import type { MediaItem } from '@/types'

const envStore = useEnvStore()
const mediaStore = useMediaStore()
const taskStore = useTaskStore()
const dragActive = ref(false)

const inputOperationIssue = computed(() =>
  envStore.operationIssue?.scope === 'input' ? envStore.operationIssue.error : null,
)

function getWorkflowSummary(item: MediaItem): string {
  const labels = [
    item.workflowConfig.interpolation.enabled ? '补帧' : null,
    item.workflowConfig.superResolution.enabled ? '超分' : null,
    item.workflowConfig.anime.enabled ? '动漫' : null,
  ].filter(Boolean)
  return labels.length > 0 ? labels.join(' / ') : WORKFLOW_LABELS[resolvePrimaryMode(item)]
}

async function reinspectSelection(): Promise<void> {
  const ids = mediaStore.selectedIds.length > 0 ? mediaStore.selectedIds : mediaStore.activeItem ? [mediaStore.activeItem.id] : []
  await mediaStore.inspectItems(ids)
}

async function handleDrop(event: DragEvent): Promise<void> {
  dragActive.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  const paths = files
    .map((file) => (file as File & { path?: string }).path)
    .filter((path): path is string => Boolean(path))

  if (paths.length > 0) {
    await mediaStore.addMediaPaths(paths)
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
          <p class="panel-caption">导入后会自动读取素材信息。复选框用于后续页面批量套用设置，激活行用于切换当前素材。</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" @click="mediaStore.selectAllMedia(!mediaStore.allSelected)">
            {{ mediaStore.allSelected ? '取消全选' : '全选全部' }}
          </button>
          <button class="ghost-button" :disabled="mediaStore.mediaItems.length === 0" @click="reinspectSelection()">
            重新读取
          </button>
          <button class="primary-button" @click="mediaStore.pickInputs()">批量导入</button>
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
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>素材列表</h2>
          <p class="panel-caption">点击行切换激活文件；勾选后的文件会在后续页面一起接收批量设置。</p>
        </div>
      </div>

      <div v-if="mediaStore.mediaItems.length === 0" class="empty-state">
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
              <th>流程</th>
              <th>状态</th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in mediaStore.mediaItems"
              :key="item.id"
              class="media-row"
              :class="{ active: item.id === mediaStore.activeItemId }"
              @click="mediaStore.setActiveItem(item.id)"
            >
              <td @click.stop>
                <input
                  :checked="item.selected"
                  type="checkbox"
                  @change="mediaStore.setItemSelected(item.id, ($event.target as HTMLInputElement).checked)"
                />
              </td>
              <td>
                <div class="table-primary">{{ item.displayName }}</div>
                <div class="table-secondary path-text">{{ item.inputPath }}</div>
              </td>
              <td>{{ item.info ? `${item.info.width}×${item.info.height}` : '--' }}</td>
              <td>{{ item.info ? `${formatNumber(item.info.fps)} FPS` : '--' }}</td>
              <td>{{ item.info?.video_codec || '--' }}</td>
              <td>{{ getWorkflowSummary(item) }}</td>
              <td>
                <span class="inline-status" :data-state="item.taskState.status">{{ item.taskState.status }}</span>
              </td>
              <td @click.stop>
                <button class="table-action" :disabled="taskStore.batch.isRunning" @click="mediaStore.removeMediaItem(item.id)">
                  移除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
