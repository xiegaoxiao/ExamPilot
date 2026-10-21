<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { NConfigProvider, NMessageProvider, NDialogProvider } from "naive-ui";
import {
  LayoutDashboard,
  BookOpen,
  Library,
  Play,
  RotateCcw,
  CalendarDays,
  ShieldCheck,
  Settings,
  GraduationCap,
  Menu,
  X,
  ChevronDown,
  ArrowUpRight,
  CircleCheck,
} from "lucide-vue-next";
import { useWorkspace } from "./stores/workspace";
import { errorText } from "./lib/api";
import tokens from "./design/design-tokens.json";
const route = useRoute(),
  store = useWorkspace();
const menu = ref(false),
  startupError = ref("");
const nav = [
  { path: "/", label: "首页", icon: LayoutDashboard },
  { path: "/courses", label: "我的课程", icon: BookOpen },
  { path: "/questions", label: "智能题库", icon: Library },
  { path: "/practice", label: "开始练习", icon: Play },
  { path: "/mistakes", label: "错题中心", icon: RotateCcw },
  { path: "/plans", label: "每日复习", icon: CalendarDays },
  { path: "/review", label: "审核中心", icon: ShieldCheck },
];
const theme = {
  common: {
    primaryColor: tokens.primitive.color.primary["500"],
    primaryColorHover: tokens.primitive.color.primary["600"],
    borderRadius: tokens.primitive.radius.control,
    fontFamily: 'Inter, "Segoe UI", "Microsoft YaHei", sans-serif',
  },
};
const today = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: store.settings?.timezone || "Asia/Shanghai",
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date()),
);
async function boot() {
  try {
    await store.refresh();
    startupError.value = "";
  } catch (e) {
    startupError.value = errorText(e);
  }
}
onMounted(boot);
</script>

<template>
  <NConfigProvider :theme-overrides="theme"
    ><NMessageProvider
      ><NDialogProvider>
        <div class="app-shell">
          <button
            v-if="menu"
            class="nav-backdrop"
            aria-label="关闭导航"
            @click="menu = false"
          ></button>
          <aside class="sidebar" :class="{ open: menu }">
            <RouterLink to="/" class="brand" @click="menu = false"
              ><span class="brand-mark"><GraduationCap :size="24" /></span
              ><span
                >Exam<span class="brand-accent">Pilot</span
                ><small>把握每一次考试</small></span
              ></RouterLink
            >
            <p class="nav-label">学习空间</p>
            <nav aria-label="主导航">
              <RouterLink
                v-for="item in nav"
                :key="item.path"
                :to="item.path"
                :class="{
                  active:
                    item.path === '/'
                      ? route.path === '/'
                      : route.path.startsWith(item.path),
                }"
                @click="menu = false"
                ><component :is="item.icon" :size="19" /><span>{{
                  item.label
                }}</span
                ><span
                  v-if="item.path === '/review' && store.pendingApproval"
                  class="nav-count"
                  >{{ store.pendingApproval }}</span
                ></RouterLink
              >
            </nav>
            <div class="sidebar-bottom">
              <div class="local-note">
                <CircleCheck :size="18" />
                <div>
                  <strong>{{
                    store.ready ? "本地工作区已连接" : "连接本地工作区"
                  }}</strong
                  ><small>学习数据留在你的电脑</small>
                </div>
              </div>
              <RouterLink
                to="/settings"
                class="settings-link"
                @click="menu = false"
                ><Settings :size="19" /> 设置与数据</RouterLink
              >
              <div class="profile">
                <span class="avatar">我</span>
                <div>
                  <strong>我的备考空间</strong><small>个人版 · 本地优先</small>
                </div>
                <span class="version-badge">DEMO</span>
              </div>
            </div>
          </aside>
          <div class="main-shell">
            <header class="topbar">
              <div class="breadcrumb">
                <button
                  class="icon-btn mobile-menu"
                  aria-label="打开导航"
                  @click="menu = !menu"
                >
                  <Menu :size="20" /></button
                ><span>学习空间</span><span class="slash">/</span
                ><strong>{{ route.meta.title }}</strong>
              </div>
              <div class="topbar-right">
                <span class="date-display">{{ today }}</span
                ><label class="course-switch" aria-label="当前课程"
                  ><BookOpen :size="16" /><select
                    :value="store.selectedId"
                    aria-label="当前课程"
                    @change="
                      store.choose(($event.target as HTMLSelectElement).value)
                    "
                  >
                    <option v-if="!store.subjects.length" value="">
                      尚无课程
                    </option>
                    <option
                      v-for="s in store.subjects"
                      :key="s.id"
                      :value="s.id"
                    >
                      {{ s.name }}
                    </option>
                  </select></label
                >
              </div>
            </header>
            <main class="page-main">
              <div class="page-heading">
                <div>
                  <p class="eyebrow">{{ route.meta.eyebrow }}</p>
                  <h1>{{ route.meta.title }}</h1>
                </div>
                <span class="local-badge"><span></span> 本地运行</span>
              </div>
              <div v-if="startupError" class="notice danger">
                <strong>无法连接本地服务</strong>
                <p>{{ startupError }}</p>
                <button class="btn secondary" @click="boot">重试连接</button>
              </div>
              <RouterView v-else-if="store.ready" :key="route.path" />
              <div v-else class="loading-block">
                <span class="spinner"></span>正在连接你的学习空间…
              </div>
              <footer class="page-footer">
                <span>ExamPilot · 让复习有依据，让进步可追踪</span
                ><span>本地 Demo · 0.1</span>
              </footer>
            </main>
          </div>
        </div>
      </NDialogProvider></NMessageProvider
    ></NConfigProvider
  >
</template>
