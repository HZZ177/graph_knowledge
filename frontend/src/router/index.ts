import type { RouteRecordRaw } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import QaLayout from '../layouts/QaLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: AdminLayout,
    children: [
      {
        path: 'processes',
        component: () => import('../views/admin/processes/ProcessList.vue'),
      },
      {
        path: 'processes/:processId',
        component: () => import('../views/admin/processes/ProcessEdit.vue'),
      },
      {
        path: 'capabilities',
        component: () => import('../views/admin/capabilities/CapabilityList.vue'),
      },
      {
        path: 'data-resources',
        component: () => import('../views/admin/data-resources/DataResourceList.vue'),
      },
    ],
  },
  {
    path: '/qa',
    component: QaLayout,
    children: [
      {
        path: '',
        component: () => import('../views/qa/Chat.vue'),
      },
    ],
  },
  {
    path: '/',
    redirect: '/qa',
  },
]

export default routes
