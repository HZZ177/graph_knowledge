<template>
  <div>
    <h2>流程编辑（占位）</h2>
    <p>当前流程 ID：{{ processId }}</p>
    <router-link to="/admin/processes">返回列表</router-link>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const processId = route.params.processId as string
</script>
