<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { NModal, useDialog, useMessage } from "naive-ui";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Clock3,
  FileQuestion,
  History,
  Pause,
  Play,
  RotateCcw,
  X,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, post, query, errorText } from "../lib/api";
import {
  answerText,
  dateTime,
  kinds,
  resultLabels,
  stateLabels,
} from "../lib/format";
import type { Attempt, Chapter, Knowledge, Question } from "../lib/types";
import StatePanel from "../components/StatePanel.vue";
import QuestionDetails from "../components/QuestionDetails.vue";
const route = useRoute(),
  store = useWorkspace(),
  message = useMessage(),
  dialog = useDialog();
const views = [
  { id: "current", label: "当前待巩固" },
  { id: "history", label: "历史错题" },
  { id: "pending", label: "待复核作答" },
  { id: "future", label: "未来复习" },
  { id: "suspended", label: "已暂停" },
  { id: "attempts", label: "全部历史" },
];
const view = ref(
    views.some((v) => v.id === route.query.view)
      ? String(route.query.view)
      : "current",
  ),
  chapter = ref(""),
  kp = ref(""),
  chapters = ref<Chapter[]>([]),
  knowledge = ref<Knowledge[]>([]),
  qs = ref<Question[]>([]),
  attempts = ref<Attempt[]>([]),
  loading = ref(false),
  error = ref(""),
  expanded = ref<string[]>([]);
const isHistory = computed(() =>
    ["history", "pending", "attempts"].includes(view.value),
  ),
  showResolve = ref(false),
  target = ref<Attempt | null>(null),
  resolution = ref({
    correct: false,
    reason: "已对照教材证据确认该作答",
    add_equivalent: false,
  }),
  saving = ref(false);
let generation = 0;
async function load() {
  const sid = store.selectedId,
    gen = ++generation;
  if (!sid) return;
  loading.value = true;
  try {
    const path = `/subjects/${sid}`;
    const data = await api<unknown[]>(
      `${path}/mistakes${query({ view: view.value, chapter_id: chapter.value, knowledge_id: kp.value })}`,
    );
    if (gen !== generation) return;
    if (isHistory.value) {
      attempts.value = data as Attempt[];
      qs.value = [];
    } else {
      qs.value = data as Question[];
      attempts.value = [];
    }
    [chapters.value, knowledge.value] = await Promise.all([
      api<Chapter[]>(`${path}/chapters`),
      api<Knowledge[]>(`${path}/knowledge`),
    ]);
    error.value = "";
  } catch (e) {
    if (gen === generation) error.value = errorText(e);
  } finally {
    if (gen === generation) loading.value = false;
  }
}
function toggle(id: string) {
  expanded.value = expanded.value.includes(id)
    ? expanded.value.filter((x) => x !== id)
    : [...expanded.value, id];
}
function resolveDialog(a: Attempt, correct: boolean, equivalent = false) {
  target.value = a;
  resolution.value = {
    correct,
    reason: "已对照教材证据确认该作答",
    add_equivalent: equivalent,
  };
  showResolve.value = true;
}
async function resolve() {
  if (!target.value) return;
  saving.value = true;
  try {
    await post(
      `/subjects/${store.selectedId}/attempts/${target.value.id}/resolve`,
      resolution.value,
    );
    message.success("复核已记录");
    showResolve.value = false;
    await Promise.all([load(), store.refresh()]);
  } catch (e) {
    message.error(errorText(e));
  } finally {
    saving.value = false;
  }
}
function pause(q: Question) {
  const paused = q.card?.state !== "suspended";
  dialog.info({
    title: paused ? "暂停自动复习" : "恢复自动复习",
    content: paused
      ? "暂停后保留历史和原到期时刻，手动练习不会自动解除暂停。"
      : "恢复原学习状态与到期时刻；若已逾期，将重新纳入到期队列。",
    positiveText: "确认",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await post(
          `/subjects/${store.selectedId}/cards/${q.question_id}/pause`,
          { paused },
        );
        await load();
      } catch (e) {
        message.error(errorText(e));
      }
    },
  });
}
watch([view, chapter, kp], load);
watch(
  () => store.selectedId,
  () => {
    chapter.value = "";
    kp.value = "";
    void load();
  },
);
onMounted(load);
</script>
<template>
  <div class="notice info">
    <div>
      <strong>错题属于你的学习历史，题目本身不会被标记成“错题”。</strong>
      <p>
        待复核填空在确认前不算正确或错误；后续答对也不会删除过去的错误记录。
      </p>
    </div>
  </div>
  <div class="tabs scroll-tabs">
    <button
      v-for="v in views"
      :key="v.id"
      :class="{ active: view === v.id }"
      @click="view = v.id"
    >
      {{ v.label }}
    </button>
  </div>
  <div class="toolbar">
    <div class="inline-actions">
      <select
        v-model="chapter"
        class="text-input compact"
        aria-label="筛选章节"
      >
        <option value="">全部章节</option>
        <option v-for="c in chapters" :key="c.id" :value="c.id">
          {{ c.name }}
        </option></select
      ><select v-model="kp" class="text-input compact" aria-label="筛选知识点">
        <option value="">全部知识点</option>
        <option
          v-for="k in knowledge.filter(
            (k) => !chapter || k.chapter_id === chapter,
          )"
          :key="k.id"
          :value="k.id"
        >
          {{ k.name }}
        </option></select
      ><span class="muted"
        >{{ isHistory ? attempts.length : qs.length }}
        {{ isHistory ? "次作答" : "道题目" }}</span
      >
    </div>
    <button class="btn secondary small" :disabled="loading" @click="load">
      <RotateCcw :size="14" />刷新
    </button>
  </div>
  <StatePanel
    v-if="loading || error"
    :loading="loading"
    :error="error"
    @retry="load"
  />
  <div v-else-if="isHistory && attempts.length" class="question-list">
    <article v-for="a in attempts" :key="a.id" class="panel question-card">
      <div class="question-topline">
        <span class="pill type">{{ kinds[a.kind] }}</span
        ><span class="question-meta"
          >{{ a.question.chapter_name }} · v{{ a.question.version }}</span
        ><span
          class="pill status"
          :class="
            a.result === 'correct'
              ? 'success'
              : a.result === 'incorrect'
                ? 'danger'
                : 'warning'
          "
          >{{ resultLabels[a.result] }}</span
        >
      </div>
      <h3>{{ a.stem }}</h3>
      <div class="attempt-answer">
        <span>你的原始答案</span><strong>{{ answerText(a.answer) }}</strong
        ><small
          >{{ dateTime(a.created_at, store.settings?.timezone) }} · 用时
          {{ a.elapsed_seconds }} 秒</small
        >
      </div>
      <p v-if="!a.question.active" class="helper-text">
        该版本未发布或已归档/失效，仅保留历史，不进入新练习。
      </p>
      <p v-if="a.resolution" class="helper-text">
        人工复核：{{ a.resolution.reason
        }}<span v-if="a.resolution.proposed_version_id">
          · 等价答案修订已送审，尚未自动发布。</span
        >
      </p>
      <QuestionDetails v-if="expanded.includes(a.id)" :question="a.question" />
      <div class="question-card-actions">
        <button class="btn text small" @click="toggle(a.id)">
          {{ expanded.includes(a.id) ? "收起教材依据" : "查看教材与参考答案"
          }}<ChevronDown :size="14" />
        </button>
        <div class="spacer"></div>
        <template v-if="a.result === 'pending_review'"
          ><button class="btn text small" @click="resolveDialog(a, true, true)">
            补充等价答案</button
          ><button class="btn secondary small" @click="resolveDialog(a, false)">
            确认错误</button
          ><button class="btn secondary small" @click="resolveDialog(a, true)">
            确认正确
          </button></template
        ><RouterLink
          v-else-if="a.question.active"
          :to="`/practice?subject=${store.selectedId}&version=${a.version_id}`"
          class="btn secondary small"
          >再次练习 <ArrowRight :size="14"
        /></RouterLink>
      </div>
    </article>
  </div>
  <div v-else-if="!isHistory && qs.length" class="question-list">
    <article v-for="q in qs" :key="q.id" class="panel question-card">
      <div class="question-topline">
        <span class="pill type">{{ kinds[q.kind] }}</span
        ><span class="question-meta">{{ q.chapter_name }}</span
        ><span class="pill neutral status">{{
          stateLabels[q.card?.state || "new"]
        }}</span>
      </div>
      <h3>{{ q.stem }}</h3>
      <p class="helper-text">
        <Clock3 :size="14" />到期
        {{ dateTime(q.card?.due_at, store.settings?.timezone) }}
      </p>
      <div class="knowledge-tags">
        <span v-for="k in q.knowledge" :key="k.id" class="text-tag">{{
          k.name
        }}</span>
      </div>
      <div class="question-card-actions">
        <button class="btn text small" @click="pause(q)">
          <Pause v-if="q.card?.state !== 'suspended'" :size="14" /><Play
            v-else
            :size="14"
          />{{ q.card?.state === "suspended" ? "恢复复习" : "暂停复习" }}
        </button>
        <div class="spacer"></div>
        <RouterLink
          :to="`/practice?subject=${store.selectedId}&version=${q.id}`"
          class="btn secondary small"
          >{{ view === "suspended" ? "手动练习" : "复习此题"
          }}<ArrowRight :size="14"
        /></RouterLink>
      </div>
    </article>
  </div>
  <StatePanel
    v-else
    :title="
      view === 'current'
        ? '当前没有到期的待巩固题'
        : view === 'pending'
          ? '没有等待人工复核的作答'
          : '这个范围还没有记录'
    "
    :description="
      view === 'current'
        ? '答错后10分钟进入到期队列；未到期内容可在未来复习查看。'
        : '所有正式作答均会保留，可调整筛选或开始一次练习。'
    "
    ><RouterLink to="/practice" class="btn secondary"
      >开始练习</RouterLink
    ></StatePanel
  >
  <NModal
    v-model:show="showResolve"
    preset="card"
    :title="resolution.correct ? '确认该填空作答正确' : '确认该填空作答错误'"
    class="form-modal"
    style="max-width: 560px"
    ><template v-if="target"
      ><p>{{ target.stem }}</p>
      <div class="attempt-answer">
        <span>原始输入</span><strong>{{ answerText(target.answer) }}</strong>
      </div>
      <label class="form-field"
        ><span>复核依据</span
        ><textarea
          v-model="resolution.reason"
          class="text-input"
          rows="3"
          required
        ></textarea></label
      ><label v-if="resolution.correct" class="checkbox-line"
        ><input
          v-model="resolution.add_equivalent"
          type="checkbox"
        />将此输入提议为可接受等价答案</label
      >
      <p v-if="resolution.add_equivalent" class="notice info">
        将创建待审题目新版本；仍需人工批准和独立发布。旧题答案和作答不被覆盖。
      </p>
      <p class="helper-text">
        复核会追加独立结论，原始作答不可覆盖；同一作答只推进一次复习。
      </p>
      <div class="modal-actions">
        <button class="btn secondary" @click="showResolve = false">取消</button
        ><button
          class="btn primary"
          :disabled="saving || !resolution.reason.trim()"
          @click="resolve"
        >
          确认复核
        </button>
      </div></template
    ></NModal
  >
</template>
