import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKBENCH_STAGES } from '@/lib/workflow'
import DeliverStageView from '@/views/DeliverStageView.vue'
import EnhanceStageView from '@/views/EnhanceStageView.vue'
import PrepareStageView from '@/views/PrepareStageView.vue'
import ResultsStageView from '@/views/ResultsStageView.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/prepare' },
    { path: '/overview', redirect: '/prepare' },
    {
      path: '/prepare',
      name: 'prepare',
      component: PrepareStageView,
      meta: { stage: WORKBENCH_STAGES[0] },
    },
    {
      path: '/enhance',
      name: 'enhance',
      component: EnhanceStageView,
      meta: { stage: WORKBENCH_STAGES[1] },
    },
    {
      path: '/deliver',
      name: 'deliver',
      component: DeliverStageView,
      meta: { stage: WORKBENCH_STAGES[2] },
    },
    {
      path: '/results',
      name: 'results',
      component: ResultsStageView,
      meta: { stage: WORKBENCH_STAGES[3] },
    },
    { path: '/source', redirect: { path: '/prepare', query: { tab: 'input' } } },
    { path: '/interpolation', redirect: { path: '/enhance', query: { section: 'interpolation' } } },
    { path: '/super-resolution', redirect: { path: '/enhance', query: { section: 'super-resolution' } } },
    { path: '/anime', redirect: { path: '/enhance', query: { section: 'anime' } } },
    { path: '/format', redirect: '/deliver' },
    { path: '/preview', redirect: '/results' },
  ],
})
