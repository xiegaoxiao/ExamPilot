<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { NModal, useDialog, useMessage } from "naive-ui";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  FileText,
  FileUp,
  Plus,
  Settings2,
  ShieldCheck,
  Star,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, post, errorText, query } from "../lib/api";
import type { Chapter, Source, Knowledge, Job } from "../lib/types";
import { dateTime } from "../lib/format";
import StatePanel from "../components/StatePanel.vue";
const route = useRoute(),
  store = useWorkspace(),
  message = useMessage(),
  dialog = useDialog(),
  sid = String(route.params.id);
const subject = computed(() => store.subjects.find((s) => s.id === sid)),
  chapters = ref<Chapter[]>([]),
  sources = ref<Source[]>([]),
  knowledge = ref<Knowledge[]>([]),
  jobs = ref<Job[]>([]);
const loading = ref(true),
  error = ref(""),
  uploading = ref(false),
  uploadChapter = ref(""),
  tab = ref("sources"),
  showChapter = ref(false),
  showSettings = ref(false),
  saving = ref(false),
  editingChapter = ref("");
const chapterForm = ref({ name: "", exam_focus: false }),
  form = ref({ name: "", exam_date: "", budget_minutes: 30 as number | null });
async function load() {
  loading.value = true;
  try {
    [chapters.value, sources.value, knowledge.value, jobs.value] =
      await Promise.all([
        api<Chapter[]>(`/subjects/${sid}/chapters`),
        api<Source[]>(`/subjects/${sid}/sources`),
        api<Knowledge[]>(`/subjects/${sid}/knowledge`),
        api<Job[]>(`/subjects/${sid}/jobs`),
      ]);
    uploadChapter.value ||= chapters.value.find((c) => !c.archived)?.id || "";
    error.value = "";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
function chapterDialog(chapter?: Chapter) {
  editingChapter.value = chapter?.id || "";
  chapterForm.value = {
    name: chapter?.name || "",
    exam_focus: chapter?.exam_focus || false,
  };
  showChapter.value = true;
}
async function saveChapter() {
  saving.value = true;
  try {
    if (editingChapter.value)
      await api(`/subjects/${sid}/chapters/${editingChapter.value}`, {
        method: "PATCH",
        body: JSON.stringify(chapterForm.value),
      });
    else await post(`/subjects/${sid}/chapters`, chapterForm.value);
    showChapter.value = false;
    tab.value = "knowledge";
    await Promise.all([load(), store.refresh()]);
    message.success("章节已保存");
  } catch (e) {
    message.error(errorText(e));
  } finally {
    saving.value = false;
  }
}
function settingsDialog() {
  if (subject.value) {
    form.value = {
      name: subject.value.name,
      exam_date: subject.value.exam_date || "",
      budget_minutes: subject.value.budget_minutes,
    };
    showSettings.value = true;
  }
}
async function saveSettings() {
  saving.value = true;
  try {
    await api(`/subjects/${sid}`, {
      method: "PATCH",
      body: JSON.stringify({
        ...form.value,
        exam_date: form.value.exam_date || null,
      }),
    });
    await store.refresh();
    showSettings.value = false;
    message.success("课程设置已保存；今日计划需主动重新规划才更新");
  } catch (e) {
    message.error(errorText(e));
  } finally {
    saving.value = false;
  }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0];
  if (!file) return;
  if (!uploadChapter.value) {
    message.warning("请先创建并选择章节");
    return;
  }
  uploading.value = true;
  try {
    const body = new FormData();
    body.append("file", file);
    const result = await api<Source>(
      `/subjects/${sid}/sources${query({ chapter_id: uploadChapter.value })}`,
      { method: "POST", body },
    );
    message.success(
      result.status === "partial"
        ? "已导入，可提取页可用，部分页不可用"
        : "教材已导入，来源已定位",
    );
    await Promise.all([load(), store.refresh()]);
  } catch (e) {
    message.error(errorText(e));
  } finally {
    uploading.value = false;
    input.value = "";
  }
}
function archiveChapter(chapter: Chapter) {
  dialog.warning({
    title: "归档章节",
    content: `归档“${chapter.name}”后不再参与新练习；原 PDF、题目版本与历史会保留。`,
    positiveText: "确认归档",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await post(`/subjects/${sid}/chapters/${chapter.id}/archive`);
        await Promise.all([load(), store.refresh()]);
      } catch (e) {
        message.error(errorText(e));
      }
    },
  });
}
onMounted(() => {
  store.choose(sid);
  void load();
});
</script>
<template>
  <RouterLink to="/courses" class="back-link"
    ><ArrowLeft :size="16" />返回我的课程</RouterLink
  ><StatePanel
    v-if="loading || error"
    :loading="loading"
    :error="error"
    @retry="load"
  /><template v-else-if="subject"
    ><section class="panel course-detail-header">
      <div class="course-glyph large"><BookOpen :size="30" /></div>
      <div>
        <span class="eyebrow">COURSE WORKSPACE</span>
        <h2>{{ subject.name }}</h2>
        <p>
          {{ subject.chapters }} 章节 · {{ subject.sources }} 份教材 · 考试
          {{ subject.exam_date || "未设置" }} · 每日
          {{ subject.budget_minutes ?? "未设置" }} 分钟
        </p>
      </div>
      <button class="btn secondary" @click="settingsDialog">
        <Settings2 :size="16" />课程设置
      </button>
    </section>
    <div class="tabs">
      <button
        v-for="t in [
          { id: 'sources', text: '教材资料' },
          { id: 'knowledge', text: '章节与知识点' },
          { id: 'jobs', text: '导入记录' },
        ]"
        :key="t.id"
        :class="{ active: tab === t.id }"
        @click="tab = t.id"
      >
        {{ t.text }}</button
      ><RouterLink :to="`/questions?subject=${sid}`" class="text-link"
        >查看课程题库 <ArrowRight :size="14"
      /></RouterLink>
    </div>
    <template v-if="tab === 'sources'"
      ><section class="panel">
        <div class="section-heading">
          <div>
            <h2>导入章节教材</h2>
            <p>支持可提取文本的 PDF，原件和物理页码完整保留</p>
          </div>
          <button class="btn secondary" @click="chapterDialog()">
            <Plus :size="16" />添加章节
          </button>
        </div>
        <div class="upload-controls">
          <label class="form-field"
            ><span>教材所属章节</span
            ><select v-model="uploadChapter" class="text-input">
              <option value="" disabled>请选择章节</option>
              <option
                v-for="c in chapters.filter((c) => !c.archived)"
                :key="c.id"
                :value="c.id"
              >
                {{ c.name }}
              </option>
            </select></label
          >
        </div>
        <label
          class="upload-zone"
          :class="{ disabled: uploading || !uploadChapter }"
          ><FileUp :size="30" /><strong>{{
            uploading ? "正在解析并核验 PDF…" : "点击选择课程 PDF"
          }}</strong>
          <p>Demo 支持不超过 50 MiB、500 页的文本 PDF。扫描页将标记不可用。</p>
          <input
            type="file"
            accept="application/pdf,.pdf"
            :disabled="uploading || !uploadChapter"
            @change="upload"
          /><span class="btn secondary">{{
            uploading ? "处理中，请稍候" : "选择 PDF 文件"
          }}</span></label
        >
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>已导入教材</h2>
            <p>{{ sources.length }} 份来源记录 · 同范围同文件不会重复导入</p>
          </div>
        </div>
        <div v-if="sources.length" class="source-list">
          <article v-for="s in sources" :key="s.id" class="source-row">
            <span class="file-glyph"><FileText :size="24" /></span>
            <div>
              <strong>{{ s.filename }}</strong>
              <p>
                {{ chapters.find((c) => c.id === s.chapter_id)?.name }} ·
                {{ s.page_count }} 页 ·
                {{ dateTime(s.created_at, store.settings?.timezone) }}
              </p>
              <small v-if="s.unavailable_pages.length" class="warning-text"
                >第 {{ s.unavailable_pages.join("、") }} 页无可提取文本</small
              >
            </div>
            <span
              class="pill"
              :class="s.status === 'ready' ? 'success' : 'warning'"
              >{{ s.status === "ready" ? "文本可用" : "部分可用" }}</span
            ><a
              class="btn secondary"
              :href="`/api/subjects/${sid}/sources/${s.id}/file`"
              target="_blank"
              rel="noopener"
              >打开原件</a
            >
          </article>
        </div>
        <StatePanel
          v-else
          title="还没有教材资料"
          description="先添加章节，再选择属于该课程的 PDF。Codex 只应处理你明确指定的材料。"
        /></section
    ></template>
    <section v-else-if="tab === 'knowledge'" class="panel">
      <div class="section-heading">
        <div>
          <h2>章节与知识点</h2>
          <p>知识点与教材证据、课程题目互相对应</p>
        </div>
        <button class="btn primary" @click="chapterDialog()">
          <Plus :size="16" />添加章节
        </button>
      </div>
      <div v-if="chapters.length" class="chapters-list">
        <article v-for="c in chapters" :key="c.id" class="chapter-row">
          <div class="chapter-title">
            <span class="chapter-number">{{
              String(c.position + 1).padStart(2, "0")
            }}</span>
            <h3>{{ c.name }}</h3>
            <span v-if="c.exam_focus" class="pill warning"
              ><Star :size="12" />考试重点</span
            ><span v-if="c.archived" class="pill neutral">已归档</span
            ><button
              v-if="!c.archived"
              class="btn text small"
              @click="chapterDialog(c)"
            >
              编辑</button
            ><button
              v-if="!c.archived"
              class="btn text small"
              @click="archiveChapter(c)"
            >
              归档
            </button>
          </div>
          <div class="knowledge-tags">
            <span
              v-for="k in knowledge.filter((k) => k.chapter_id === c.id)"
              :key="k.id"
              class="pill neutral"
              >{{ k.name }}</span
            ><span
              v-if="!knowledge.some((k) => k.chapter_id === c.id)"
              class="muted"
              >暂无知识点，可通过受控 CLI 导入带来源的知识点。</span
            >
          </div>
        </article>
      </div>
      <StatePanel v-else title="先为课程添加一个章节" />
    </section>
    <section v-else class="panel">
      <div class="section-heading">
        <div>
          <h2>受控导入记录</h2>
          <p>按批次追踪新增、跳过、待审与失败结果</p>
        </div>
      </div>
      <div v-if="jobs.length" class="job-list">
        <article v-for="j in jobs" :key="j.id">
          <div>
            <strong>{{ j.key }}</strong>
            <p>
              输入 {{ j.result.input || 0 }} · 新增
              {{ j.result.inserted || 0 }} · 跳过 {{ j.result.skipped || 0 }} ·
              待审 {{ j.result.needs_review || 0 }}
            </p>
            <p v-if="j.result.reason" class="danger-text">
              {{ j.result.reason }}
            </p>
          </div>
          <span
            class="pill"
            :class="j.status === 'completed' ? 'success' : 'danger'"
            >{{ j.status === "completed" ? "已完成" : "失败" }}</span
          ><small>{{ dateTime(j.created_at, store.settings?.timezone) }}</small>
        </article>
      </div>
      <StatePanel
        v-else
        title="还没有结构化导入记录"
        description="Codex 通过 CLI 导入题目后，处理结果会在这里显示。"
      />
    </section> </template
  ><StatePanel v-else title="课程不存在或已归档" />
  <NModal
    v-model:show="showChapter"
    preset="card"
    title="章节设置"
    class="form-modal"
    style="max-width: 480px"
    ><form @submit.prevent="saveChapter">
      <div class="form-field">
        <label for="chapter-name">章节名称</label
        ><input
          id="chapter-name"
          v-model="chapterForm.name"
          class="text-input"
          required
          maxlength="80"
        />
      </div>
      <label class="checkbox-line"
        ><input
          v-model="chapterForm.exam_focus"
          type="checkbox"
        />标记为考试重点章节</label
      >
      <p class="helper-text">
        仅在考前 0–7 天、同一优先层内影响顺序，不改变到期时间或预算（Demo 临时
        D-16 实现）。
      </p>
      <div class="modal-actions">
        <button
          type="button"
          class="btn secondary"
          @click="showChapter = false"
        >
          取消</button
        ><button class="btn primary" :disabled="saving">保存章节</button>
      </div>
    </form></NModal
  >
  <NModal
    v-model:show="showSettings"
    preset="card"
    title="课程设置"
    class="form-modal"
    style="max-width: 480px"
    ><form @submit.prevent="saveSettings">
      <div class="form-field">
        <label for="edit-name">课程名称</label
        ><input
          id="edit-name"
          v-model="form.name"
          class="text-input"
          required
          maxlength="80"
        />
      </div>
      <div class="form-field">
        <label for="edit-exam">考试日期</label
        ><input
          id="edit-exam"
          v-model="form.exam_date"
          type="date"
          class="text-input"
        />
      </div>
      <div class="form-field">
        <label for="edit-budget">每日复习预算（分钟）</label
        ><input
          id="edit-budget"
          v-model.number="form.budget_minutes"
          type="number"
          min="0"
          max="240"
          class="text-input"
        />
      </div>
      <div class="modal-actions">
        <button
          type="button"
          class="btn secondary"
          @click="showSettings = false"
        >
          取消</button
        ><button class="btn primary" :disabled="saving">保存设置</button>
      </div>
    </form></NModal
  >
</template>
