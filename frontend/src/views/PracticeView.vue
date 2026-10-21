<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useMessage } from "naive-ui";
import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  CircleCheck,
  CircleX,
  Clock3,
  Play,
  RotateCcw,
  ShieldCheck,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, post, query, errorText } from "../lib/api";
import { kinds, resultLabels, dateTime } from "../lib/format";
import type { Answer, Attempt, Card, Chapter, Question } from "../lib/types";
import AnswerInput from "../components/AnswerInput.vue";
import QuestionDetails from "../components/QuestionDetails.vue";
import StatePanel from "../components/StatePanel.vue";
const route = useRoute(),
  store = useWorkspace(),
  message = useMessage(),
  chapters = ref<Chapter[]>([]),
  questions = ref<Question[]>([]),
  chapter = ref(""),
  kind = ref(typeof route.query.kind === "string" ? route.query.kind : ""),
  limit = ref(10);
const loading = ref(false),
  error = ref(""),
  started = ref(false),
  index = ref(0),
  answer = ref<Answer>(null),
  result = ref<Attempt | null>(null),
  card = ref<Card | null>(null),
  submitting = ref(false),
  startedAt = ref(Date.now()),
  successCount = ref(0);
const current = computed(() => questions.value[index.value]),
  done = computed(() => started.value && index.value >= questions.value.length);
type Submission = {
  version_id: string;
  answer: Answer;
  request_id: string;
  elapsed_seconds: number;
};
const frozen = ref<Submission | null>(null);
const canSubmit = computed(
  () =>
    answer.value !== null &&
    (!Array.isArray(answer.value) || answer.value.length > 0) &&
    (typeof answer.value !== "string" || answer.value.trim().length > 0),
);
async function loadChapters() {
  if (store.selectedId)
    try {
      chapters.value = await api<Chapter[]>(
        `/subjects/${store.selectedId}/chapters`,
      );
    } catch (e) {
      message.error(errorText(e));
    }
}
async function start() {
  if (!store.selectedId) return;
  loading.value = true;
  error.value = "";
  try {
    questions.value = await api<Question[]>(
      `/subjects/${store.selectedId}/practice${query({ chapter_id: chapter.value, kind: kind.value, limit: limit.value, version_id: typeof route.query.version === "string" ? route.query.version : "" })}`,
    );
    if (!questions.value.length) {
      message.info("当前范围没有有效已发布题，请先到审核中心批准并发布");
      return;
    }
    index.value = 0;
    started.value = true;
    successCount.value = 0;
    reset();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
function reset() {
  answer.value = null;
  result.value = null;
  card.value = null;
  frozen.value = null;
  startedAt.value = Date.now();
}
async function submit() {
  if (!current.value || !canSubmit.value || submitting.value) return;
  submitting.value = true;
  try {
    frozen.value ||= {
      version_id: current.value.id,
      answer: answer.value,
      request_id: crypto.randomUUID(),
      elapsed_seconds: Math.min(
        86400,
        Math.floor((Date.now() - startedAt.value) / 1000),
      ),
    };
    result.value = await post<Attempt>(
      `/subjects/${store.selectedId}/attempts`,
      frozen.value,
    );
    if (result.value.result === "correct") successCount.value++;
    const cards = await api<Card[]>(`/subjects/${store.selectedId}/cards`);
    card.value =
      cards.find((c) => c.question_id === current.value?.question_id) || null;
    await store.refresh();
  } catch (e) {
    message.error(errorText(e));
  } finally {
    submitting.value = false;
  }
}
function next() {
  index.value++;
  reset();
}
function stop() {
  started.value = false;
  questions.value = [];
  reset();
}
watch(
  () => store.selectedId,
  () => {
    chapter.value = "";
    stop();
    void loadChapters();
  },
);
onMounted(() => {
  if (
    typeof route.query.subject === "string" &&
    store.subjects.some((s) => s.id === route.query.subject)
  )
    store.choose(route.query.subject);
  void loadChapters();
});
</script>
<template>
  <div class="practice-container">
    <section v-if="!started" class="panel practice-setup">
      <span class="setup-icon"><Play :size="30" /></span>
      <h2>开启一次专注练习</h2>
      <p>只选取已人工批准并正式发布的有效题目，作答结果实时保存。</p>
      <div class="form-field">
        <label>当前课程</label>
        <div class="selected-course">
          {{ store.selected?.name || "请先创建课程" }}
        </div>
      </div>
      <div class="two-columns">
        <label class="form-field"
          ><span>练习章节</span
          ><select v-model="chapter" class="text-input">
            <option value="">全部章节</option>
            <option
              v-for="c in chapters.filter((c) => !c.archived)"
              :key="c.id"
              :value="c.id"
            >
              {{ c.name }}
            </option>
          </select></label
        ><label class="form-field"
          ><span>题型</span
          ><select v-model="kind" class="text-input">
            <option value="">全部题型</option>
            <option v-for="(name, id) in kinds" :key="id" :value="id">
              {{ name }}
            </option>
          </select></label
        >
      </div>
      <label class="form-field"
        ><span>练习题量</span
        ><input
          v-model.number="limit"
          type="number"
          min="1"
          max="100"
          class="text-input"
      /></label>
      <p v-if="error" class="notice danger">{{ error }}</p>
      <button
        class="btn primary full-width"
        :disabled="loading || !store.selectedId || limit < 1 || limit > 100"
        @click="start"
      >
        <Play :size="16" />{{ loading ? "正在准备…" : "开始练习" }}
      </button>
      <p class="setup-note">
        <ShieldCheck :size="14" /> 普通练习无需 AI 在线 · 所有历史可追溯
      </p>
    </section>
    <section v-else-if="done" class="panel practice-complete">
      <span class="completion-icon"><CheckCheck :size="38" /></span>
      <p class="eyebrow">SESSION COMPLETE</p>
      <h2>一次专注，已经完成</h2>
      <p>
        本轮完成 {{ questions.length }} 道题，其中
        {{
          successCount
        }}
        道确认正确。<br />所有作答均已保存；待复核填空将独立处理。
      </p>
      <div class="inline-actions">
        <button class="btn secondary" @click="stop">
          <RotateCcw :size="16" />再练一组</button
        ><RouterLink to="/mistakes" class="btn primary"
          >查看待巩固 <ArrowRight :size="16"
        /></RouterLink>
      </div>
    </section>
    <template v-else-if="current"
      ><div class="practice-progress">
        <button class="btn text" @click="stop">
          <ArrowLeft :size="16" />结束本轮</button
        ><span>{{ store.selected?.name }}</span
        ><strong>{{ index + 1 }} / {{ questions.length }}</strong>
      </div>
      <div class="progress-track">
        <span :style="{ width: `${(index / questions.length) * 100}%` }"></span>
      </div>
      <section class="panel active-question">
        <div class="question-topline">
          <span class="pill type">{{ kinds[current.kind] }}</span
          ><span class="question-meta"
            >{{ current.chapter_name }} · v{{ current.version }}</span
          ><span class="pill success">有效已发布</span>
        </div>
        <h2>{{ current.stem }}</h2>
        <p class="answer-hint">
          {{
            current.kind === "multiple"
              ? "请选择所有正确选项，完全匹配才判正确。"
              : current.kind === "fill"
                ? "保留术语大小写；未命中已审核答案会进入待复核。"
                : current.kind === "boolean"
                  ? "请选择正确或错误。"
                  : "请选择一个最符合教材依据的答案。"
          }}
        </p>
        <AnswerInput
          v-model="answer"
          :kind="current.kind"
          :options="current.options"
          :disabled="submitting || !!result || !!frozen"
        />
        <div
          v-if="result"
          class="result-panel"
          :class="
            result.result === 'correct'
              ? 'success'
              : result.result === 'incorrect'
                ? 'danger'
                : 'warning'
          "
        >
          <CircleCheck v-if="result.result === 'correct'" :size="23" /><CircleX
            v-else-if="result.result === 'incorrect'"
            :size="23"
          /><Clock3 v-else :size="23" />
          <div>
            <strong>{{ resultLabels[result.result] }}</strong>
            <p v-if="result.result === 'pending_review'">
              本次输入已原样保存，不计入错题或推进复习。请到错题中心的待复核页确认。
            </p>
            <p v-else-if="card">
              {{
                card.state === "suspended"
                  ? "该题已暂停；手动作答不改变自动调度。"
                  : `下次复习：${dateTime(card.due_at, store.settings?.timezone)}`
              }}
            </p>
          </div>
        </div>
        <QuestionDetails v-if="result" :question="result.question" />
        <div class="practice-actions">
          <span>{{
            result
              ? "已保存本次作答与版本依据"
              : "提交后查看答案、解析和教材证据"
          }}</span
          ><button
            v-if="!result"
            class="btn primary"
            :disabled="!canSubmit || submitting"
            @click="submit"
          >
            {{ submitting ? "正在保存…" : frozen ? "重试同次提交" : "提交答案"
            }}<ArrowRight :size="16" /></button
          ><button v-else class="btn primary" @click="next">
            {{ index === questions.length - 1 ? "完成本轮" : "下一题"
            }}<ArrowRight :size="16" />
          </button>
        </div></section
    ></template>
  </div>
</template>
