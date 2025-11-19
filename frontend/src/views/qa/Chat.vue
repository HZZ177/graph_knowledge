<template>
  <div class="chat-page">
    <h2>业务流程问答（示例）</h2>
    <div class="controls">
      <label>
        流程 ID：
        <input v-model="processId" placeholder="例如 c_open_card" />
      </label>
    </div>
    <div class="chat-box">
      <textarea
        v-model="question"
        rows="3"
        placeholder="请输入你的问题"
      ></textarea>
      <button @click="send" :disabled="loading || !question">发送</button>
    </div>
    <div class="answer" v-if="answer">
      <h3>回答：</h3>
      <p>{{ answer }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { chat } from '../../api/chat'

const question = ref('')
const processId = ref('c_open_card')
const answer = ref('')
const loading = ref(false)

const send = async () => {
  loading.value = true
  try {
    const res = await chat({ question: question.value, process_id: processId.value || null })
    answer.value = res.answer
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-page {
  max-width: 800px;
}
.controls {
  margin-bottom: 8px;
}
.chat-box {
  margin-bottom: 16px;
}
.chat-box textarea {
  width: 100%;
  box-sizing: border-box;
}
.answer {
  padding: 12px;
  border-radius: 4px;
  background-color: #f7f7f7;
}
</style>
