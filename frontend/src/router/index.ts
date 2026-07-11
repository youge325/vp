import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKBENCH_MODULES } from '@/views/registry'

// 模块视图全部走懒加载，预处理/后处理共享同一个 stage 视图分块。
const HomeModuleView = () => import('@/views/HomeModuleView.vue')
const InputModuleView = () => import('@/views/InputModuleView.vue')
const DecodeModuleView = () => import('@/views/DecodeModuleView.vue')
const StageModuleView = () => import('@/views/StageModuleView.vue')
const EnhanceModuleView = () => import('@/views/EnhanceModuleView.vue')
const EncodeModuleView = () => import('@/views/EncodeModuleView.vue')
const RenderModuleView = () => import('@/views/RenderModuleView.vue')

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    {
      path: '/home',
      name: 'home',
      component: HomeModuleView,
      meta: { module: WORKBENCH_MODULES[0] },
    },
    {
      path: '/input',
      name: 'input',
      component: InputModuleView,
      meta: { module: WORKBENCH_MODULES[1] },
    },
    {
      path: '/decode',
      name: 'decode',
      component: DecodeModuleView,
      meta: { module: WORKBENCH_MODULES[2] },
    },
    {
      path: '/preprocess',
      name: 'preprocess',
      component: StageModuleView,
      props: { stage: 'preprocess' },
      meta: { module: WORKBENCH_MODULES[3] },
    },
    {
      path: '/enhance',
      name: 'enhance',
      component: EnhanceModuleView,
      meta: { module: WORKBENCH_MODULES[4] },
    },
    {
      path: '/postprocess',
      name: 'postprocess',
      component: StageModuleView,
      props: { stage: 'postprocess' },
      meta: { module: WORKBENCH_MODULES[5] },
    },
    {
      path: '/encode',
      name: 'encode',
      component: EncodeModuleView,
      meta: { module: WORKBENCH_MODULES[6] },
    },
    {
      path: '/render',
      name: 'render',
      component: RenderModuleView,
      meta: { module: WORKBENCH_MODULES[7] },
    },
  ],
})
