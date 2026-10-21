import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./style.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: () => import("./views/DashboardView.vue"),
      meta: { title: "学习概览", eyebrow: "你的备考驾驶舱" },
    },
    {
      path: "/courses",
      component: () => import("./views/CoursesView.vue"),
      meta: { title: "我的课程", eyebrow: "让每门课都有自己的复习节奏" },
    },
    {
      path: "/courses/:id",
      component: () => import("./views/CourseDetailView.vue"),
      meta: { title: "课程工作区", eyebrow: "教材、章节与知识点" },
    },
    {
      path: "/questions",
      component: () => import("./views/QuestionsView.vue"),
      meta: { title: "智能题库", eyebrow: "每一道题，都有据可查" },
    },
    {
      path: "/review",
      component: () => import("./views/QuestionsView.vue"),
      meta: { title: "审核中心", eyebrow: "让可靠的题目进入正式题库" },
    },
    {
      path: "/practice",
      component: () => import("./views/PracticeView.vue"),
      meta: { title: "开始练习", eyebrow: "用一次专注，确认真正掌握" },
    },
    {
      path: "/mistakes",
      component: () => import("./views/MistakesView.vue"),
      meta: { title: "错题中心", eyebrow: "把每一次错误，变成下一次进步" },
    },
    {
      path: "/plans",
      component: () => import("./views/PlansView.vue"),
      meta: { title: "每日复习", eyebrow: "在有限时间里，复习最需要的内容" },
    },
    {
      path: "/settings",
      component: () => import("./views/SettingsView.vue"),
      meta: { title: "设置", eyebrow: "本地数据与学习偏好" },
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
createApp(App).use(createPinia()).use(router).mount("#app");
