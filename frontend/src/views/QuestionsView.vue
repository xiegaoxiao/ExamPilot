<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { NModal, useDialog, useMessage } from "naive-ui";
import {
  Check,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  History,
  ListFilter,
  Send,
  ShieldCheck,
  X,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, post, query, errorText } from "../lib/api";
import { dateTime, kinds, statusLabels } from "../lib/format";
import type { Audit, Chapter, Knowledge, Question } from "../lib/types";
import StatePanel from "../components/StatePanel.vue";
import QuestionDetails from "../components/QuestionDetails.vue";
const route = useRoute(),
  store = useWorkspace(),
  dialog = useDialog(),
  message = useMessage();
const reviewing = computed(() => route.path === "/review"),
  questions = ref<Question[]>([]),
  chapters = ref<Chapter[]>([]),
  knowledge = ref<Knowledge[]>([]);
const selected = ref<string[]>([]),
  expanded = ref<string[]>([]),
  loading = ref(false),
  error = ref(""),
  busy = ref(false),
  auditShow = ref(false),
  audits = ref<Audit[]>([]),
  auditLoading = ref(false);
const filters = ref({ chapter_id: "", kind: "", knowledge_id: "", status: "" });
let generation = 0;
async function load() {
  const sid = store.selectedId,
    gen = ++generation;
  if (!sid) {
    questions.value = [];
    return;
  }
  loading.value = true;
  try {
    const [qs, cs, ks] = await Promise.all([
      api<Question[]>(`/subjects/${sid}/questions${query(filters.value)}`),
      api<Chapter[]>(`/subjects/${sid}/chapters`),
      api<Knowledge[]>(`/subjects/${sid}/knowledge`),
    ]);
    if (gen !== generation) return;
    questions.value = qs;
    chapters.value = cs;
    knowledge.value = ks;
    selected.value = [];
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
function selectAll(status: string) {
  selected.value = questions.value
    .filter((q) => q.status === status)
    .map((q) => q.id);
  if (!selected.value.length) message.info("当前筛选下没有符合状态的题目");
}
const actions: Record<
  string,
  { title: string; confirm: string; success: string }
> = {
  approve: {
    title: "批量批准题目",
    confirm: "确认批准",
    success: "批量批准成功",
  },
  publish: { title: "独立发布题目", confirm: "确认发布", success: "发布成功" },
  reject: { title: "拒绝题目", confirm: "确认拒绝", success: "已记录拒绝" },
  archive: { title: "归档题目", confirm: "确认归档", success: "题目已归档" },
  validate: { title: "重新校验", confirm: "确认校验", success: "校验已完成" },
};
function action(action: string, ids = selected.value) {
  if (!ids.length) return;
  const config = actions[action]!,
    rows = questions.value.filter((q) => ids.includes(q.id));
  const sid = store.selectedId;
  dialog.warning({
    title: config.title,
    content: `当前课程：${store.selected?.name}。本次操作 ${rows.length} 个明确版本：${rows.map((q) => `${q.stem}（v${q.version}）`).join("；")}。${action === "approve" ? "请对照原教材核验答案；批准不会自动发布。" : action === "publish" ? "发布后才能参与正式练习；硬性校验失败将拒绝整个本次操作。" : "历史作答和来源不会被删除。"}`,
    positiveText: config.confirm,
    negativeText: "取消",
    onPositiveClick: async () => {
      busy.value = true;
      try {
        await post(`/subjects/${sid}/review`, {
          ids: [...ids],
          action,
          reason: "用户在审核中心明确操作并核对题目来源",
        });
        message.success(config.success);
        await Promise.all([load(), store.refresh()]);
      } catch (e) {
        message.error(errorText(e));
      } finally {
        busy.value = false;
      }
    },
  });
}
async function showAudit(q: Question) {
  auditShow.value = true;
  auditLoading.value = true;
  try {
    audits.value = await api<Audit[]>(
      `/subjects/${store.selectedId}/questions/${q.id}/audit`,
    );
  } catch (e) {
    message.error(errorText(e));
    auditShow.value = false;
  } finally {
    auditLoading.value = false;
  }
}
watch(
  () => store.selectedId,
  () => {
    filters.value = { chapter_id: "", kind: "", knowledge_id: "", status: "" };
    void load();
  },
);
watch(filters, load, { deep: true });
onMounted(() => {
  if (
    typeof route.query.subject === "string" &&
    store.subjects.some((s) => s.id === route.query.subject)
  )
    store.choose(route.query.subject);
  void load();
});
</script>
<template>
  <section v-if="reviewing" class="review-intro">
    <span class="section-icon"><ShieldCheck :size="24" /></span>
    <div>
      <h2>AI 协助生成，你来决定发布</h2>
      <p>自动校验只提供质量检查。请核对教材证据，再明确批准、独立发布。</p>
    </div>
    <div class="review-flow">
      <span>生成草稿</span><i>→</i><span>自动校验</span><i>→</i
      ><strong>人工批准</strong><i>→</i><strong>正式发布</strong>
    </div>
  </section>
  <section class="panel filter-panel">
    <div class="filter-title">
      <ListFilter :size="17" />筛选题目<span>{{
        store.selected?.name || "请先建立课程"
      }}</span>
    </div>
    <div class="filter-grid">
      <label
        ><span>章节</span
        ><select v-model="filters.chapter_id" class="text-input">
          <option value="">全部章节</option>
          <option v-for="c in chapters" :key="c.id" :value="c.id">
            {{ c.name }}
          </option>
        </select></label
      ><label
        ><span>题型</span
        ><select v-model="filters.kind" class="text-input">
          <option value="">全部题型</option>
          <option v-for="(name, id) in kinds" :key="id" :value="id">
            {{ name }}
          </option>
        </select></label
      ><label
        ><span>知识点</span
        ><select v-model="filters.knowledge_id" class="text-input">
          <option value="">全部知识点</option>
          <option
            v-for="k in knowledge.filter(
              (k) => !filters.chapter_id || k.chapter_id === filters.chapter_id,
            )"
            :key="k.id"
            :value="k.id"
          >
            {{ k.name }}
          </option>
        </select></label
      ><label
        ><span>审核状态</span
        ><select v-model="filters.status" class="text-input">
          <option value="">全部状态</option>
          <option v-for="(name, id) in statusLabels" :key="id" :value="id">
            {{ name }}
          </option>
        </select></label
      >
    </div>
  </section>
  <div class="toolbar">
    <div class="inline-actions">
      <span class="muted">共 {{ questions.length }} 个题目版本</span
      ><template v-if="reviewing"
        ><button class="btn text small" @click="selectAll('needs_review')">
          选择全部待审题</button
        ><button class="btn text small" @click="selectAll('approved')">
          选择全部已批准题</button
        ><button
          v-if="selected.length"
          class="btn text small"
          @click="selected = []"
        >
          清除选择
        </button></template
      >
    </div>
    <div v-if="reviewing" class="inline-actions">
      <span v-if="selected.length" class="muted"
        >已选 {{ selected.length }} 题</span
      ><button
        class="btn secondary"
        :disabled="!selected.length || busy"
        @click="action('approve')"
      >
        <CheckCheck :size="16" />批准所选</button
      ><button
        class="btn primary"
        :disabled="!selected.length || busy"
        @click="action('publish')"
      >
        <Send :size="15" />发布所选
      </button>
    </div>
  </div>
  <StatePanel
    v-if="loading || error"
    :loading="loading"
    :error="error"
    @retry="load"
  />
  <div v-else-if="questions.length" class="question-list">
    <article
      v-for="q in questions"
      :key="q.id"
      class="panel question-card"
      :class="{ selected: selected.includes(q.id) }"
    >
      <div class="question-topline">
        <label v-if="reviewing" class="question-check"
          ><input
            v-model="selected"
            type="checkbox"
            :value="q.id"
            :aria-label="`选择题目：${q.stem}`" /></label
        ><span class="pill type">{{ kinds[q.kind] }}</span
        ><span class="question-meta"
          >{{ q.chapter_name }} · v{{ q.version }}</span
        ><span
          class="pill status"
          :class="
            q.status === 'published'
              ? 'success'
              : q.status === 'needs_review'
                ? 'warning'
                : 'neutral'
          "
          >{{ statusLabels[q.status] }}</span
        >
      </div>
      <h3>{{ q.stem }}</h3>
      <div class="knowledge-tags">
        <span v-for="k in q.knowledge" :key="k.id" class="text-tag">{{
          k.name
        }}</span
        ><span v-if="q.issues?.length" class="danger-text"
          >{{ q.issues.length }} 项校验问题</span
        ><span v-else-if="q.status === 'needs_review'" class="muted"
          ><FileCheck2 :size="13" />自动检查无硬性问题，仍需人工核验</span
        >
      </div>
      <QuestionDetails v-if="expanded.includes(q.id)" :question="q" />
      <div class="question-card-actions">
        <button class="btn text small" @click="toggle(q.id)">
          {{ expanded.includes(q.id) ? "收起详情" : "查看答案与教材证据"
          }}<ChevronUp v-if="expanded.includes(q.id)" :size="14" /><ChevronDown
            v-else
            :size="14"
          /></button
        ><button class="btn text small" @click="showAudit(q)">
          <History :size="14" />审核记录
        </button>
        <div class="spacer"></div>
        <template v-if="reviewing"
          ><button
            v-if="q.status === 'needs_review'"
            class="btn text small danger-text"
            :disabled="busy"
            @click="action('reject', [q.id])"
          >
            拒绝</button
          ><button
            v-if="q.status === 'needs_review'"
            class="btn secondary small"
            :disabled="busy"
            @click="action('approve', [q.id])"
          >
            批准此题</button
          ><button
            v-if="q.status === 'approved'"
            class="btn secondary small"
            :disabled="busy"
            @click="action('publish', [q.id])"
          >
            独立发布</button
          ><button
            v-if="q.status === 'published'"
            class="btn text small"
            :disabled="busy"
            @click="action('archive', [q.id])"
          >
            归档
          </button></template
        ><RouterLink
          v-else-if="q.active"
          :to="`/practice?subject=${q.subject_id}&version=${q.id}`"
          class="btn secondary small"
          >练习此题</RouterLink
        >
      </div>
    </article>
  </div>
  <StatePanel
    v-else
    title="当前范围还没有题目"
    description="上传课程教材后，可让外部 Codex 整理知识点并通过 CLI 导入结构化题目。"
    ><RouterLink to="/courses" class="btn secondary"
      >查看课程资料</RouterLink
    ></StatePanel
  >
  <NModal
    v-model:show="auditShow"
    preset="card"
    title="题目审核与发布记录"
    class="form-modal"
    style="max-width: 640px"
    ><StatePanel v-if="auditLoading" loading />
    <div v-else class="audit-list">
      <div v-for="a in audits" :key="a.id">
        <span class="audit-dot"></span>
        <div>
          <strong>{{
            {
              import_draft: "导入草稿",
              validate: "自动校验",
              approve: "人工批准",
              publish: "独立发布",
              reject: "拒绝",
              archive: "归档",
              revise: "建立修订版本",
              superseded: "被新版本替代",
            }[a.action] || a.action
          }}</strong>
          <p>
            {{ a.actor }} ·
            {{ dateTime(a.created_at, store.settings?.timezone) }}
          </p>
          <pre v-if="Object.keys(a.details).length">{{
            JSON.stringify(a.details, null, 2)
          }}</pre>
        </div>
      </div>
    </div></NModal
  >
</template>
