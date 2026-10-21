import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "../lib/api";
import type { Settings, Subject } from "../lib/types";
export const useWorkspace = defineStore("workspace", () => {
  const subjects = ref<Subject[]>([]);
  const selectedId = ref(localStorage.getItem("exampilot.subject") || "");
  const settings = ref<Settings | null>(null);
  const ready = ref(false);
  const selected = computed(() =>
    subjects.value.find((s) => s.id === selectedId.value),
  );
  const pendingApproval = computed(() =>
    subjects.value.reduce((n, s) => n + s.needs_review, 0),
  );
  async function refresh() {
    const [courses, config] = await Promise.all([
      api<Subject[]>("/subjects"),
      api<Settings>("/settings"),
    ]);
    subjects.value = courses;
    settings.value = config;
    if (!courses.some((s) => s.id === selectedId.value))
      choose(courses[0]?.id || "");
    ready.value = true;
  }
  function choose(id: string) {
    selectedId.value = id;
    localStorage.setItem("exampilot.subject", id);
  }
  return {
    subjects,
    selectedId,
    selected,
    settings,
    ready,
    pendingApproval,
    refresh,
    choose,
  };
});
