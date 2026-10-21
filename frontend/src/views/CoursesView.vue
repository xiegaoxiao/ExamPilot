<script setup lang="ts">
import { ref } from "vue";
import { NModal, useMessage } from "naive-ui";
import {
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Clock3,
  Plus,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { post, errorText } from "../lib/api";
import type { Subject } from "../lib/types";
import StatePanel from "../components/StatePanel.vue";
const store = useWorkspace(),
  message = useMessage(),
  show = ref(false),
  saving = ref(false);
const form = ref({ name: "", exam_date: "", budget_minutes: 30 });
async function save() {
  saving.value = true;
  try {
    await post<Subject>("/subjects", {
      ...form.value,
      exam_date: form.value.exam_date || null,
    });
    await store.refresh();
    show.value = false;
    form.value = { name: "", exam_date: "", budget_minutes: 30 };
    message.success("课程已创建");
  } catch (e) {
    message.error(errorText(e));
  } finally {
    saving.value = false;
  }
}
</script>
<template>
  <div class="toolbar">
    <p class="muted">
      {{ store.subjects.length }} 门课程 · 各自管理教材、题库与复习进度
    </p>
    <button class="btn primary" @click="show = true">
      <Plus :size="17" />新建课程
    </button>
  </div>
  <div v-if="store.subjects.length" class="course-grid">
    <RouterLink
      v-for="s in store.subjects"
      :key="s.id"
      :to="`/courses/${s.id}`"
      class="course-card"
      ><div class="course-card-top">
        <span class="course-glyph"><BookOpen :size="26" /></span
        ><span
          v-if="s.days_to_exam !== null"
          class="pill"
          :class="
            s.days_to_exam >= 0 && s.days_to_exam <= 7 ? 'warning' : 'neutral'
          "
          >{{
            s.days_to_exam < 0
              ? "考试已过"
              : s.days_to_exam === 0
                ? "今日考试"
                : `还有 ${s.days_to_exam} 天`
          }}</span
        ><ArrowUpRight v-else :size="18" class="muted" />
      </div>
      <h2>{{ s.name }}</h2>
      <p>
        {{ s.chapters }} 个章节 · {{ s.sources }} 份教材 ·
        {{ s.knowledge }} 个知识点
      </p>
      <div class="course-card-stats">
        <div>
          <strong>{{ s.published }}</strong
          ><small>正式题目</small>
        </div>
        <div>
          <strong>{{ s.accuracy === null ? "—" : `${s.accuracy}%` }}</strong
          ><small>作答正确率</small>
        </div>
        <div>
          <strong>{{ s.due }}</strong
          ><small>当前到期</small>
        </div>
      </div>
      <div class="course-progress-label">
        <span>练习覆盖率</span><strong>{{ s.coverage }}%</strong>
      </div>
      <div class="progress-track">
        <span :style="{ width: `${s.coverage}%` }"></span>
      </div>
      <div class="course-card-footer">
        <span
          ><Clock3 :size="14" />{{ s.budget_minutes ?? "未设置" }} 分钟/日</span
        ><span
          ><CalendarDays :size="14" />{{ s.exam_date || "未设考试日期" }}</span
        >
      </div></RouterLink
    >
  </div>
  <StatePanel
    v-else
    title="从第一门课程开始"
    description="为课程建立独立的知识范围，导入教材后即可让 Codex 协助整理知识和题目。"
  />
  <NModal
    v-model:show="show"
    preset="card"
    title="新建课程"
    class="form-modal"
    style="max-width: 480px"
    ><form @submit.prevent="save">
      <div class="form-field">
        <label for="course-name">课程名称</label
        ><input
          id="course-name"
          v-model="form.name"
          class="text-input"
          placeholder="例如：软件需求工程"
          required
          maxlength="80"
        />
      </div>
      <div class="form-field">
        <label for="course-exam">考试日期（可选）</label
        ><input
          id="course-exam"
          v-model="form.exam_date"
          type="date"
          class="text-input"
        />
      </div>
      <div class="form-field">
        <label for="course-budget">每日复习预算（分钟）</label
        ><input
          id="course-budget"
          v-model.number="form.budget_minutes"
          type="number"
          min="0"
          max="240"
          class="text-input"
          required
        /><small>预算为 0 时暂停自动排题，仍可手动练习。</small>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn secondary" @click="show = false">
          取消</button
        ><button class="btn primary" :disabled="saving">
          {{ saving ? "保存中…" : "保存课程" }}
        </button>
      </div>
    </form></NModal
  >
</template>
