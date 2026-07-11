<script setup lang="ts">
import { ref } from 'vue'
import { useMediaImport } from '@/composables/app/useMediaImport'
import { useMediaListEditor } from '@/composables/forms/useMediaListEditor'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import IssueBanner from '@/components/IssueBanner.vue'

const listEditor = useMediaListEditor()
const mediaStore = useMediaStore()
const { pickAndImport, importPaths, reinspectIds } = useMediaImport()
const inputIssue = useOperationIssue('input')
const runStateStore = useMediaRunState()
const dragActive = ref(false)

function statusOf(id: string): string {
  return runStateStore.getByItemId(id)?.taskState.status ?? 'idle'
}

async function handleDrop(event: DragEvent): Promise<void> {
  dragActive.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  const paths = files
    .map((file) => (file as File & { path?: string }).path)
    .filter((path): path is string => Boolean(path))
  if (paths.length > 0) {
    await importPaths(paths)
  }
}

function handleDragOver(event: DragEvent): void {
  event.preventDefault()
  dragActive.value = true
}

function handleDragLeave(): void {
  dragActive.value = false
}

async function reinspectSelection(): Promise<void> {
  const ids = mediaStore.selectedIds.length > 0
    ? mediaStore.selectedIds
    : mediaStore.activeItem
      ? [mediaStore.activeItem.id]
      : []
  await reinspectIds(ids)
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>批量导入</h2>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" @click="mediaStore.selectAll(!mediaStore.allSelected)">
            {{ mediaStore.allSelected ? '取消全选' : '全选全部' }}
          </button>
          <button class="ghost-button" :disabled="mediaStore.mediaItems.length === 0" @click="reinspectSelection()">
            重新读取
          </button>
          <button class="primary-button" @click="pickAndImport">批量导入</button>
        </div>
      </div>

      <div
        class="dropzone"
        :class="{ active: dragActive }"
        @drop.prevent="handleDrop"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
      >
        <strong>拖放视频到这里，或使用"批量导入"按钮</strong>
      </div>

      <IssueBanner :issue="inputIssue" title="批量导入失败" />
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>素材列表</h2>
        </div>
      </div>

      <div v-if="mediaStore.mediaItems.length === 0" class="empty-state">
        <strong>还没有素材</strong>
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
              @click="mediaStore.setActive(item.id)"
            >
              <td @click.stop>
                <input
                  :checked="item.selected"
                  type="checkbox"
                  @change="mediaStore.setSelected(item.id, ($event.target as HTMLInputElement).checked)"
                />
              </td>
              <td>
                <div class="table-primary">{{ item.displayName }}</div>
                <div class="table-secondary path-text">{{ item.inputPath }}</div>
              </td>
              <td>{{ item.info ? `${item.info.width}×${item.info.height}` : '--' }}</td>
              <td>{{ listEditor.fpsLabelOf(item) }}</td>
              <td>{{ item.info?.videoCodec || '--' }}</td>
              <td>{{ listEditor.workflowLabelOf(item) }}</td>
              <td>
                <span class="inline-status" :data-state="statusOf(item.id)">{{ statusOf(item.id) }}</span>
              </td>
              <td @click.stop>
                <button class="table-action" @click="listEditor.removeItem(item.id)">
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
