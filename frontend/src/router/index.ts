import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import type { ModuleKey } from '@/config/workbench-modules'
import { WORKBENCH_MODULE_BY_KEY, WORKBENCH_MODULES } from '@/views/registry'

// 模块视图全部走懒加载，预处理/后处理共享同一个 stage 视图分块。
const HomeModuleView = () => import('@/views/HomeModuleView.vue')
const InputModuleView = () => import('@/views/InputModuleView.vue')
const DecodeModuleView = () => import('@/views/DecodeModuleView.vue')
const StageModuleView = () => import('@/views/StageModuleView.vue')
const EnhanceModuleView = () => import('@/views/EnhanceModuleView.vue')
const EncodeModuleView = () => import('@/views/EncodeModuleView.vue')
const RenderModuleView = () => import('@/views/RenderModuleView.vue')

const MODULE_VIEW_CONFIG = {
  home: { component: HomeModuleView },
  input: { component: InputModuleView },
  decode: { component: DecodeModuleView },
  preprocess: { component: StageModuleView, props: { stage: 'preprocess' } },
  enhance: { component: EnhanceModuleView },
  postprocess: { component: StageModuleView, props: { stage: 'postprocess' } },
  encode: { component: EncodeModuleView },
  render: { component: RenderModuleView },
} as const satisfies Record<ModuleKey, { component: () => Promise<unknown>; props?: Record<string, string> }>

const moduleRoutes: RouteRecordRaw[] = WORKBENCH_MODULES.map((module) => {
  const view = MODULE_VIEW_CONFIG[module.key]
  return {
    path: module.path,
    name: module.key,
    component: view.component,
    ...('props' in view ? { props: view.props } : {}),
    meta: { module },
  }
})

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: WORKBENCH_MODULE_BY_KEY.home.path },
    ...moduleRoutes,
  ],
})
