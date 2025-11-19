<template>
  <div class="qa-layout">
    <header class="header">
      <h1>业务流程问答</h1>
      <router-link to="/admin/processes">进入管理后台</router-link>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.qa-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #eee;
}
.main {
  flex: 1;
  padding: 16px;
  box-sizing: border-box;
}
</style>
