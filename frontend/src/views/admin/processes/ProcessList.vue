<template>
  <div>
    <h2>流程列表（示例）</h2>
    <p>下面数据来自后端 /api/v1/processes。</p>
    <button @click="load">刷新</button>
    <ul>
      <li v-for="p in processes" :key="p.process_id">
        <router-link :to="`/admin/processes/${p.process_id}`">
          {{ p.process_id }} - {{ p.name }}
        </router-link>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listProcesses } from '../../../api/processes'

interface ProcessItem {
  process_id: string
  name: string
}

const processes = ref<ProcessItem[]>([])

const load = async () => {
  processes.value = await listProcesses()
}

onMounted(load)
</script>
