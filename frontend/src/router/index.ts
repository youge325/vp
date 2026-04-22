import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import EncodeModuleView from '@/views/DeliverStageView.vue'
import EnhanceModuleView from '@/views/EnhanceStageView.vue'
import InputModuleView from '@/views/InputModuleView.vue'
import HomeModuleView from '@/views/PrepareStageView.vue'
import PreviewModuleView from '@/views/PreviewModuleView.vue'
import RenderModuleView from '@/views/ResultsStageView.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/overview', redirect: '/home' },
    { path: '/prepare', redirect: '/home' },
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
      path: '/enhance',
      name: 'enhance',
      component: EnhanceModuleView,
      meta: { module: WORKBENCH_MODULES[2] },
    },
    {
      path: '/encode',
      name: 'encode',
      component: EncodeModuleView,
      meta: { module: WORKBENCH_MODULES[3] },
    },
    {
      path: '/render',
      name: 'render',
      component: RenderModuleView,
      meta: { module: WORKBENCH_MODULES[4] },
    },
    {
      path: '/preview',
      name: 'preview',
      component: PreviewModuleView,
      meta: { module: WORKBENCH_MODULES[5] },
    },
    { path: '/source', redirect: '/input' },
    { path: '/interpolation', redirect: { path: '/enhance', query: { section: 'interpolation' } } },
    { path: '/super-resolution', redirect: { path: '/enhance', query: { section: 'super-resolution' } } },
    { path: '/anime', redirect: { path: '/enhance', query: { section: 'anime' } } },
    { path: '/format', redirect: '/encode' },
    { path: '/deliver', redirect: '/encode' },
    { path: '/results', redirect: '/render' },
  ],
})
