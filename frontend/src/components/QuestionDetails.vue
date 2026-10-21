<script setup lang="ts">
import { FileText, ExternalLink, ShieldCheck } from "lucide-vue-next";
import { answerText } from "../lib/format";
import type { Question } from "../lib/types";
defineProps<{ question: Question }>();
</script>
<template>
  <div class="question-details">
    <div v-if="question.options.length" class="read-options">
      <div
        v-for="o in question.options"
        :key="o.id"
        :class="{
          correct: Array.isArray(question.answer)
            ? question.answer.includes(o.id)
            : question.answer === o.id,
        }"
      >
        <strong>{{ o.id }}</strong
        >{{ o.text }}
      </div>
    </div>
    <div class="answer-explanation">
      <span class="field-caption">参考答案</span
      ><strong>{{ answerText(question.answer) }}</strong>
      <p>{{ question.explanation }}</p>
    </div>
    <div class="knowledge-tags">
      <span v-for="k in question.knowledge" :key="k.id" class="pill neutral">{{
        k.name
      }}</span>
    </div>
    <div v-for="(e, i) in question.evidence" :key="i" class="evidence-box">
      <div>
        <FileText :size="16" /><strong>{{ e.filename || "教材来源" }}</strong
        ><span>PDF 第 {{ e.page }} 页</span
        ><a
          :href="`/api/subjects/${question.subject_id}/sources/${e.source_id}/file#page=${e.page}`"
          target="_blank"
          rel="noopener"
          title="查看原 PDF"
          ><ExternalLink :size="15"
        /></a>
      </div>
      <blockquote>{{ e.quote }}</blockquote>
    </div>
    <p v-if="!question.evidence?.length" class="notice warning">
      缺少教材证据，不能发布。
    </p>
    <ul v-if="question.issues?.length" class="issue-list">
      <li v-for="issue in question.issues" :key="issue">{{ issue }}</li>
    </ul>
  </div>
</template>
