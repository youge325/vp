<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useWorkbenchStore } from '@/stores/workbench'

const router = useRouter()
const store = useWorkbenchStore()

function goTo(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="page-grid">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">概览</p>
        <h2>围绕 CLI 内核重新搭起的 Tauri 工作台</h2>
        <p class="lead">
          这一版把旧 Gradio 和 PyQt 交互硬替换成多步工作台，Tauri 只负责选文件、拉起后端进程、转发事件和打包资源。
        </p>
      </div>

      <div class="hero-actions">
        <button class="primary-button" :disabled="store.env.isChecking" @click="store.checkEnvironment()">
          {{ store.env.isChecking ? '检查中…' : '检查环境' }}
        </button>
        <button class="ghost-button" @click="goTo('/source')">导入素材</button>
      </div>
    </section>

    <section class="card-grid card-grid-wide">
      <article class="surface-subpanel feature-card">
        <p class="summary-title">运行时</p>
        <strong>{{ store.env.checkResult?.runtime?.mode ?? '尚未检测' }}</strong>
        <p class="subtle">
          {{ store.env.checkResult?.runtime?.python_executable ?? '等待检查 Python / bundled runtime' }}
        </p>
      </article>
      <article class="surface-subpanel feature-card">
        <p class="summary-title">素材状态</p>
        <strong>{{ store.source.inputPath ? '已有素材' : '未导入' }}</strong>
        <p class="subtle">{{ store.source.info ? `${store.source.info.width}x${store.source.info.height}` : '等待读取视频信息' }}</p>
      </article>
      <article class="surface-subpanel feature-card">
        <p class="summary-title">任务状态</p>
        <strong>{{ store.task.status }}</strong>
        <p class="subtle">{{ store.task.error?.message ?? '主链路支持启动、取消、完成和错误态。' }}</p>
      </article>
    </section>

    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">工作台建议顺序</p>
          <h3>先环境，后素材，再流程，最后执行</h3>
        </div>
      </div>

      <div class="step-cards">
        <button class="step-card" @click="goTo('/source')">
          <span>02</span>
          <strong>导入素材并读取视频信息</strong>
        </button>
        <button class="step-card" @click="goTo('/interpolation')">
          <span>03</span>
          <strong>调补帧参数和目标帧率</strong>
        </button>
        <button class="step-card" @click="goTo('/super-resolution')">
          <span>04</span>
          <strong>决定是否串联超分步骤</strong>
        </button>
        <button class="step-card" @click="goTo('/deliver')">
          <span>07</span>
          <strong>统一确认编码和输出并启动任务</strong>
        </button>
      </div>
    </section>
  </div>
</template>
