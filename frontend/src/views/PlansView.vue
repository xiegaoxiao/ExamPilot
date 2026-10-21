<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NModal, useDialog, useMessage } from "naive-ui";
import {
  ArrowRight,
  CalendarDays,
  CheckCheck,
  Clock3,
  MoreHorizontal,
  RotateCcw,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, post, errorText } from "../lib/api";
import { kinds, reasonLabels, tomorrow } from "../lib/format";
import type { Plan, PlanItem } from "../lib/types";
import StatePanel from "../components/StatePanel.vue";
const store = useWorkspace(),
  message = useMessage(),
  dialog = useDialog(),
  plans = ref<Plan[]>([]),
  day = ref(""),
  today = ref(""),
  loading = ref(false),
  error = ref(""),
  busy = ref(false),
  showDefer = ref(false),
  target = ref<PlanItem | null>(null),
  until = ref("");
const plan = computed(() => plans.value.find((p) => p.day === day.value)),
  historical = computed(() => day.value !== today.value),
  completed = computed(
    () => plan.value?.items.filter((i) => i.status === "completed").length || 0,
  );
async function load() {
  const sid = store.selectedId;
  if (!sid) return;
  loading.value = true;
  try {
    const current = await post<Plan>(`/subjects/${sid}/plan`);
    today.value = current.day;
    plans.value = await api<Plan[]>(`/subjects/${sid}/plans`);
    if (!plans.value.some((p) => p.day === day.value)) day.value = current.day;
    error.value = "";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
function replan() {
  dialog.warning({
    title: "重新规划今日复习",
    content:
      "将按当前有效题库、到期状态和预算重新计算；保留已完成、延期和手工移除的记录。不会伪造作答或改写到期时间。",
    positiveText: "确认重新规划",
    negativeText: "取消",
    onPositiveClick: async () => {
      busy.value = true;
      try {
        await post(`/subjects/${store.selectedId}/plan`, { replan: true });
        day.value = today.value;
        await load();
        message.success("今日计划已重新规划");
      } catch (e) {
        message.error(errorText(e));
      } finally {
        busy.value = false;
      }
    },
  });
}
function defer(item: PlanItem) {
  target.value = item;
  until.value = tomorrow(today.value);
  showDefer.value = true;
}
async function edit(item: PlanItem, action: string) {
  busy.value = true;
  try {
    await post(`/subjects/${store.selectedId}/plan/items/${item.id}`, {
      action,
      ...(action === "defer" ? { until: until.value } : {}),
    });
    showDefer.value = false;
    await load();
    message.success("计划调整已保存");
  } catch (e) {
    message.error(errorText(e));
  } finally {
    busy.value = false;
  }
}
function remove(item: PlanItem) {
  dialog.warning({
    title: "移出今日计划",
    content:
      "只移除今日安排，不删除题目，也不产生作答或掌握度；次日可按原到期时间重新评估。",
    positiveText: "确认移出",
    negativeText: "取消",
    onPositiveClick: () => edit(item, "remove"),
  });
}
watch(
  () => store.selectedId,
  () => {
    day.value = "";
    void load();
  },
);
onMounted(load);
</script>
<template>
  <div class="toolbar">
    <div class="inline-actions">
      <CalendarDays :size="19" /><select
        v-model="day"
        class="text-input compact"
        aria-label="计划日期"
      >
        <option v-for="p in plans" :key="p.id" :value="p.day">
          {{ p.day }}{{ p.day === today ? " · 今日" : " · 历史" }}
        </option>
      </select>
    </div>
    <button
      class="btn primary"
      :disabled="busy || !store.selectedId"
      @click="replan"
    >
      <RotateCcw :size="16" />重新规划今日
    </button>
  </div>
  <StatePanel
    v-if="loading || error"
    :loading="loading"
    :error="error"
    @retry="load"
  /><template v-else-if="plan"
    ><section class="plan-summary">
      <div>
        <span class="eyebrow">{{
          historical ? "保留的学习足迹" : "TODAY’S STUDY PLAN"
        }}</span>
        <h2>{{ store.selected?.name }}</h2>
        <p>
          {{ plan.day }} · {{ plan.timezone }} · 第 {{ plan.revision }} 次规划
        </p>
      </div>
      <div class="plan-summary-stats">
        <div>
          <strong
            >{{ plan.minutes
            }}<small>/ {{ plan.budget_minutes ?? "未配置" }}</small></strong
          ><span>预计 / 预算分钟</span>
        </div>
        <div>
          <strong
            >{{ completed
            }}<small
              >/
              {{
                plan.items.filter((i) =>
                  ["pending", "completed"].includes(i.status),
                ).length
              }}</small
            ></strong
          ><span>已完成任务</span>
        </div>
      </div>
    </section>
    <p class="helper-text">
      到期题 → 薄弱知识点新题 →
      其他新题。刷新不会覆盖手工调整；题库变化后请主动重新规划。
    </p>
    <div v-if="historical" class="notice info">
      历史计划仅供查看，真实作答与人工延期记录保留。
    </div>
    <section v-if="plan.items.length" class="panel">
      <div class="section-heading">
        <div>
          <h2>学习任务</h2>
          <p>完成状态由真实有效作答更新，不能手动勾选成“已掌握”</p>
        </div>
        <span class="pill neutral">{{ plan.items.length }} 项记录</span>
      </div>
      <div class="plan-task-list">
        <article
          v-for="(item, i) in plan.items"
          :key="item.id"
          class="plan-task"
          :class="{
            done: item.status === 'completed',
            inactive:
              !item.active || ['deferred', 'removed'].includes(item.status),
          }"
        >
          <span class="task-number"
            ><CheckCheck
              v-if="item.status === 'completed'"
              :size="20"
            /><template v-else>{{
              String(i + 1).padStart(2, "0")
            }}</template></span
          >
          <div class="plan-task-main">
            <div class="inline-actions">
              <span class="pill type">{{ kinds[item.kind] }}</span
              ><span class="helper-text">{{
                { due: "到期优先", weak_new: "薄弱知识点新题", new: "新题" }[
                  item.priority
                ] || item.priority
              }}</span
              ><span v-if="!item.active" class="pill warning">版本已失效</span>
            </div>
            <h3>{{ item.stem }}</h3>
            <p>
              <Clock3 :size="13" />预计 {{ item.minutes }} 分钟<span
                v-if="item.until"
              >
                · 已调整至 {{ item.until }}</span
              ><span v-if="item.status === 'completed'"> · 已有真实作答</span>
            </p>
          </div>
          <div class="plan-task-actions">
            <template v-if="!historical"
              ><template v-if="item.status === 'pending'"
                ><button
                  class="btn text small"
                  :disabled="busy"
                  @click="defer(item)"
                >
                  延期</button
                ><button
                  class="btn text small"
                  :disabled="busy"
                  @click="remove(item)"
                >
                  移出</button
                ><RouterLink
                  v-if="item.active"
                  :to="`/practice?subject=${store.selectedId}&version=${item.version_id}`"
                  class="btn secondary small"
                  >开始 <ArrowRight :size="14" /></RouterLink></template
              ><button
                v-else-if="
                  item.status === 'deferred' || item.status === 'removed'
                "
                class="btn text small"
                :disabled="busy"
                @click="edit(item, 'restore')"
              >
                恢复到今日</button
              ><span v-else class="pill success">已完成</span></template
            ><span v-else class="pill neutral">{{
              {
                pending: "未完成",
                completed: "已完成",
                deferred: "已延期",
                removed: "已移出",
              }[item.status]
            }}</span>
          </div>
        </article>
      </div>
    </section>
    <StatePanel
      v-else
      title="这一天还没有可安排的任务"
      :description="
        !plan.budget_minutes
          ? '当前预算为0或尚未配置，自动排题已暂停；可到课程设置调整。'
          : '请先发布题目，或等待复习卡到期；你也可以手动练习已发布题。'
      "
      ><RouterLink to="/review" class="btn secondary"
        >查看题目审核</RouterLink
      ></StatePanel
    >
    <section v-if="plan.skipped.length" class="panel">
      <div class="section-heading">
        <div>
          <h2>本轮未安排</h2>
          <p>跳过任务不会被视为已完成，也不会改变复习到期时间</p>
        </div>
      </div>
      <div class="skipped-list">
        <div v-for="(item, i) in plan.skipped" :key="i">
          <strong>{{ item.stem }}</strong
          ><span
            >{{ reasonLabels[item.reason] || item.reason
            }}{{ item.until ? `，至 ${item.until}` : "" }}</span
          >
        </div>
      </div>
    </section></template
  ><StatePanel
    v-else
    title="请先创建一门课程"
    description="每个科目有独立的分钟预算，今日计划在打开页面时生成。"
  />
  <NModal
    v-model:show="showDefer"
    preset="card"
    title="延期复习任务"
    class="form-modal"
    style="max-width: 480px"
  >
    <template v-if="target">
      <p>{{ target.stem }}</p>
      <label class="form-field" style="margin-top: 24px"
        ><span>重新安排的学习日</span
        ><input
          v-model="until"
          type="date"
          class="text-input"
          :min="tomorrow(today)"
          required
          aria-label="延期日期"
      /></label>
      <p class="helper-text">
        保留本次人工意图至指定日期；仅影响自动排入计划的资格，不改变题目原始到期时间或作答历史。
      </p>
      <div class="modal-actions">
        <button class="btn secondary" @click="showDefer = false">取消</button
        ><button
          class="btn primary"
          :disabled="busy || !until || until <= today"
          @click="edit(target, 'defer')"
        >
          保存延期
        </button>
      </div>
    </template>
  </NModal>
</template>
