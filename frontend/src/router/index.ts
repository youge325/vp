import { createRouter, createWebHashHistory } from 'vue-router'
import { WORKFLOW_STEPS } from '@/lib/workflow'
import AnimeView from '@/views/AnimeView.vue'
import FormatView from '@/views/FormatView.vue'
import InterpolationView from '@/views/InterpolationView.vue'
import OutputRunView from '@/views/OutputRunView.vue'
import OverviewView from '@/views/OverviewView.vue'
import PreviewView from '@/views/PreviewView.vue'
import SourceView from '@/views/SourceView.vue'
import SuperResolutionView from '@/views/SuperResolutionView.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewView, meta: { step: WORKFLOW_STEPS[0] } },
    { path: '/source', name: 'source', component: SourceView, meta: { step: WORKFLOW_STEPS[1] } },
    {
      path: '/interpolation',
      name: 'interpolation',
      component: InterpolationView,
      meta: { step: WORKFLOW_STEPS[2] },
    },
    {
      path: '/super-resolution',
      name: 'super-resolution',
      component: SuperResolutionView,
      meta: { step: WORKFLOW_STEPS[3] },
    },
    { path: '/anime', name: 'anime', component: AnimeView, meta: { step: WORKFLOW_STEPS[4] } },
    { path: '/format', name: 'format', component: FormatView, meta: { step: WORKFLOW_STEPS[5] } },
    {
      path: '/deliver',
      name: 'deliver',
      component: OutputRunView,
      meta: { step: WORKFLOW_STEPS[6] },
    },
    {
      path: '/preview',
      name: 'preview',
      component: PreviewView,
      meta: { step: WORKFLOW_STEPS[7] },
    },
  ],
})
