<template>
  <div class="layout">
    <aside class="sidebar">
      <h2>管理后台</h2>
      <nav>
        <router-link to="/admin/processes">流程管理</router-link>
        <router-link to="/admin/capabilities">能力管理</router-link>
        <router-link to="/admin/data-resources">数据资源</router-link>
        <router-link to="/qa">切换到问答</router-link>
      </nav>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
}
.sidebar {
  width: 220px;
  padding: 16px;
  border-right: 1px solid #eee;
  box-sizing: border-box;
}
.sidebar h2 {
  margin-top: 0;
}
.sidebar a {
  display: block;
  margin: 4px 0;
}
.content {
  flex: 1;
  padding: 16px;
  box-sizing: border-box;
}
</style>
