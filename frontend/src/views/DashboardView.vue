<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarClock,
  CheckCheck,
  Clock3,
  FileQuestion,
  GraduationCap,
  History,
  ListChecks,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-vue-next";
import { api, errorText } from "../lib/api";
import { dateTime, kinds, resultLabels } from "../lib/format";
import type { Dashboard } from "../lib/types";
import StatePanel from "../components/StatePanel.vue";
import ActivityChart from "../components/ActivityChart.vue";
import { useWorkspace } from "../stores/workspace";
const store = useWorkspace(),
  data = ref<Dashboard | null>(null),
  loading = ref(true),
  error = ref("");
async function load() {
  loading.value = true;
  try {
    data.value = await api<Dashboard>("/dashboard");
    error.value = "";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
const planCount = computed(
  () =>
    data.value?.plans.reduce(
      (n, p) =>
        n + p.items.filter((i) => i.status === "pending" && i.active).length,
      0,
    ) || 0,
);
const plannedMinutes = computed(
  () => data.value?.plans.reduce((n, p) => n + p.minutes, 0) || 0,
);
const completed = computed(
  () =>
    data.value?.plans.reduce(
      (n, p) => n + p.items.filter((i) => i.status === "completed").length,
      0,
    ) || 0,
);
const weekTotal = computed(
  () => data.value?.activity.reduce((n, a) => n + a.count, 0) || 0,
);
const totalItems = computed(
  () =>
    data.value?.plans.reduce(
      (n, p) =>
        n +
        p.items.filter((i) => ["pending", "completed"].includes(i.status))
          .length,
      0,
    ) || 0,
);
const nextAction = computed(() => {
  const totals = data.value?.totals;
  if (planCount.value) return { to: "/plans", label: "开始今日复习" };
  if (totals?.needs_review) return { to: "/review", label: "审核我的题目" };
  if (totals?.approved) return { to: "/review", label: "发布已批准题" };
  if (totals?.published) return { to: "/plans", label: "规划今日复习" };
  return { to: "/courses", label: "建立我的课程" };
});
onMounted(load);
</script>
<template>
  <StatePanel
    v-if="loading || error"
    :loading="loading"
    :error="error"
    @retry="load"
  />
  <template v-else-if="data">
    <section class="welcome-hero">
      <div class="hero-copy">
        <span class="hero-kicker"
          ><Sparkles :size="15" /> 让每一分钟复习都有方向</span
        >
        <h2>今天的进步，<br />从一次专注开始。</h2>
        <p v-if="planCount">
          已为你安排 {{ planCount }} 道练习，预计
          {{ plannedMinutes }} 分钟。<br />跟随计划，把知识一点点变成底气。
        </p>
        <p v-else-if="data.totals.needs_review">
          教材与练习已准备好。先审核题目，<br />让每一道进入练习的题都有可靠依据。
        </p>
        <p v-else-if="data.totals.approved">
          题目已经过人工批准，<br />请再执行独立发布，正式开启练习。
        </p>
        <p v-else-if="data.totals.published">
          正式题库已就绪。你可以重新规划今日，<br />也可以手动开始一组专注练习。
        </p>
        <p v-else>建立你的课程、导入教材，<br />开启属于你的期末备考节奏。</p>
        <RouterLink :to="nextAction.to" class="btn primary"
          >{{ nextAction.label }}<ArrowRight :size="17"
        /></RouterLink>
      </div>
      <div class="hero-visual" aria-hidden="true">
        <div class="orbit orbit-one"></div>
        <div class="orbit orbit-two"></div>
        <div class="floating-label">
          <ShieldCheck :size="17" /> 有据可查的知识
        </div>
        <div class="hero-book">
          <GraduationCap :size="76" :stroke-width="1.3" />
        </div>
        <div class="floating-label lower">
          <CheckCheck :size="17" /> 可追踪的每一步
        </div>
      </div>
      <div class="hero-progress">
        <div
          class="progress-dial"
          :style="{
            '--progress': `${totalItems ? (completed / totalItems) * 100 : 0}%`,
          }"
        >
          <strong
            >{{ completed }}<small>/ {{ totalItems }}</small></strong
          >
        </div>
        <span>今日计划完成</span>
      </div>
    </section>
    <div class="stats-grid">
      <article class="stat-card">
        <div>
          <span>当前到期复习</span
          ><strong>{{ data.totals.due }}<small>题</small></strong>
          <p>按真实到期时间计算</p>
        </div>
        <span class="stat-icon"><CalendarClock :size="22" /></span>
      </article>
      <article class="stat-card">
        <div>
          <span>累计练习</span
          ><strong>{{ data.totals.attempts }}<small>次</small></strong>
          <p>每次作答都有记录</p>
        </div>
        <span class="stat-icon success"><ListChecks :size="22" /></span>
      </article>
      <article class="stat-card">
        <div>
          <span>历史错误作答</span
          ><strong>{{ data.totals.history_wrong }}<small>次</small></strong>
          <p>答对后依然保留历史</p>
        </div>
        <span class="stat-icon warning"><History :size="22" /></span>
      </article>
      <article class="stat-card">
        <div>
          <span>待人工复核</span
          ><strong>{{ data.totals.pending }}<small>次</small></strong>
          <p>未判定，不计入错题</p>
        </div>
        <span class="stat-icon"><FileQuestion :size="22" /></span>
      </article>
    </div>
    <div class="dashboard-grid">
      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>我的课程</h2>
            <p>独立的知识范围，一致的学习节奏</p>
          </div>
          <RouterLink to="/courses" class="text-link"
            >管理课程 <ArrowUpRight :size="15"
          /></RouterLink>
        </div>
        <div v-if="data.subjects.length" class="dashboard-courses">
          <RouterLink
            v-for="s in data.subjects"
            :key="s.id"
            :to="`/courses/${s.id}`"
            class="course-row"
            ><span class="course-glyph"><BookOpen :size="22" /></span>
            <div class="course-row-main">
              <h3>{{ s.name }}</h3>
              <p>
                {{ s.chapters }} 个章节<span>·</span
                >{{ s.published }} 道正式题<span>·</span
                >{{ s.budget_minutes ?? "未设置" }} 分钟/日
              </p>
              <div class="progress-track">
                <span :style="{ width: `${s.coverage}%` }"></span>
              </div>
            </div>
            <div class="course-row-end">
              <span
                v-if="s.days_to_exam !== null"
                class="pill"
                :class="
                  s.days_to_exam >= 0 && s.days_to_exam <= 7
                    ? 'warning'
                    : 'neutral'
                "
                >{{
                  s.days_to_exam < 0
                    ? "考试已过"
                    : s.days_to_exam === 0
                      ? "今日考试"
                      : `距考试 ${s.days_to_exam} 天`
                }}</span
              ><small>练习覆盖 {{ s.coverage }}%</small>
            </div></RouterLink
          >
        </div>
        <StatePanel
          v-else
          title="你的第一门课程，等待启航"
          description="课程之间独立管理，教材与题目都能回到原始出处。"
          ><RouterLink to="/courses" class="btn secondary"
            >添加课程</RouterLink
          ></StatePanel
        >
      </section>
      <section class="panel weekly-panel">
        <div class="section-heading">
          <div>
            <h2>最近 7 天</h2>
            <p>每一份投入，都算数</p>
          </div>
          <TrendingUp :size="20" class="muted" />
        </div>
        <div class="week-number">{{ weekTotal }}<small>次练习</small></div>
        <ActivityChart :rows="data.activity" />
        <p class="chart-footnote">
          <span class="legend-dot"></span>实际作答次数 · 包含待复核作答
        </p>
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>今日学习计划</h2>
            <p>{{ data.day }} · 各科预算独立计算</p>
          </div>
          <RouterLink to="/plans" class="text-link"
            >查看计划 <ArrowRight :size="15"
          /></RouterLink>
        </div>
        <div v-if="data.plans.some((p) => p.items.length)" class="plan-preview">
          <template v-for="p in data.plans" :key="p.id"
            ><div
              v-for="item in p.items.slice(0, 3)"
              :key="item.id"
              class="preview-task"
            >
              <span
                class="task-marker"
                :class="{ done: item.status === 'completed' }"
                ><CheckCheck
                  v-if="item.status === 'completed'"
                  :size="14" /><Clock3 v-else :size="14"
              /></span>
              <div>
                <strong>{{ item.stem }}</strong
                ><small
                  >{{
                    data.subjects.find((s) => s.id === p.subject_id)?.name
                  }}
                  · {{ kinds[item.kind] }}</small
                >
              </div>
              <span class="pill neutral">{{
                item.status === "completed"
                  ? "已完成"
                  : item.status === "pending"
                    ? `${item.minutes} 分钟`
                    : "已调整"
              }}</span>
            </div></template
          >
        </div>
        <StatePanel
          v-else
          title="今日计划还没有任务"
          description="先审核发布题目，再到每日复习中点击重新规划。已完成的计划和真实作答都会保留。"
          ><RouterLink to="/plans" class="text-link"
            >前往每日复习 <ArrowRight :size="16" /></RouterLink
        ></StatePanel>
      </section>
      <section class="panel next-step">
        <span class="section-icon"><Target :size="24" /></span>
        <h2>每一步，都值得信任</h2>
        <p>题目附带教材证据，AI 负责协助，<br />你来决定哪些题进入正式练习。</p>
        <div class="mini-metric">
          <span>正式题库</span><strong>{{ data.totals.published }} 题</strong>
        </div>
        <div class="mini-metric">
          <span>待人工审核</span
          ><strong>{{ data.totals.needs_review }} 题</strong>
        </div>
        <RouterLink to="/review" class="btn secondary full-width"
          >前往审核中心 <ArrowRight :size="16"
        /></RouterLink>
      </section>
    </div>
    <section v-if="data.recent.length" class="panel recent-panel">
      <div class="section-heading">
        <div>
          <h2>最近练习</h2>
          <p>原始答案、判题版本和复核结论均可追溯</p>
        </div>
        <RouterLink to="/mistakes?view=attempts" class="text-link"
          >查看全部历史 <ArrowRight :size="15"
        /></RouterLink>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>题目</th>
              <th>课程</th>
              <th>结果</th>
              <th>作答时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in data.recent.slice(0, 5)" :key="a.id">
              <td class="table-stem">{{ a.stem }}</td>
              <td>{{ a.subject_name }}</td>
              <td>
                <span
                  class="pill"
                  :class="
                    a.result === 'correct'
                      ? 'success'
                      : a.result === 'incorrect'
                        ? 'danger'
                        : 'warning'
                  "
                  >{{ resultLabels[a.result] }}</span
                >
              </td>
              <td class="muted">{{ dateTime(a.created_at, data.timezone) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>
