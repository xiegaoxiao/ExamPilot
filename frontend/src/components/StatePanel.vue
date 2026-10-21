<script setup lang="ts">
import { BookOpen, AlertCircle } from "lucide-vue-next";
defineProps<{
  loading?: boolean;
  error?: string;
  title?: string;
  description?: string;
}>();
defineEmits<{ retry: [] }>();
</script>
<template>
  <div class="state-panel">
    <template v-if="loading"
      ><span class="spinner"></span>
      <h3>正在整理学习数据…</h3></template
    ><template v-else
      ><span class="empty-icon"
        ><AlertCircle v-if="error" :size="26" /><BookOpen v-else :size="26"
      /></span>
      <h3>{{ error ? "暂时无法加载" : title || "这里还没有内容" }}</h3>
      <p>
        {{
          error ||
          description ||
          "从一份教材、一道练习开始，逐步建立你的复习闭环。"
        }}
      </p>
      <button v-if="error" class="btn secondary" @click="$emit('retry')">
        重新加载</button
      ><slot v-else
    /></template>
  </div>
</template>
