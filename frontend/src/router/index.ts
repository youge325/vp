import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import DecodeModuleView from '@/views/DecodeModuleView.vue'
import EncodeModuleView from '@/views/EncodeModuleView.vue'
import EnhanceModuleView from '@/views/EnhanceModuleView.vue'
import HomeModuleView from '@/views/HomeModuleView.vue'
import InputModuleView from '@/views/InputModuleView.vue'
import PostprocessModuleView from '@/views/PostprocessModuleView.vue'
import PreprocessModuleView from '@/views/PreprocessModuleView.vue'
import RenderModuleView from '@/views/RenderModuleView.vue'

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
      component: PreprocessModuleView,
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
      component: PostprocessModuleView,
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
