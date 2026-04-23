import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import DecodeModuleView from '@/views/DecodeModuleView.vue'
import EncodeModuleView from '@/views/EncodeModuleView.vue'
import EnhanceModuleView from '@/views/EnhanceModuleView.vue'
import HomeModuleView from '@/views/HomeModuleView.vue'
import InputModuleView from '@/views/InputModuleView.vue'
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
      path: '/enhance',
      name: 'enhance',
      component: EnhanceModuleView,
      meta: { module: WORKBENCH_MODULES[3] },
    },
    {
      path: '/encode',
      name: 'encode',
      component: EncodeModuleView,
      meta: { module: WORKBENCH_MODULES[4] },
    },
    {
      path: '/render',
      name: 'render',
      component: RenderModuleView,
      meta: { module: WORKBENCH_MODULES[5] },
    },
  ],
})
