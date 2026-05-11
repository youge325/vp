import 'vue-router'
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

declare module 'vue-router' {
  interface RouteMeta {
    module?: WorkbenchModuleDefinition
  }
}
