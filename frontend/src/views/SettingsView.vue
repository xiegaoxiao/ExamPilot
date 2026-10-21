<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useMessage } from "naive-ui";
import {
  Database,
  FolderOpen,
  Globe2,
  HardDrive,
  LockKeyhole,
  Save,
} from "lucide-vue-next";
import { useWorkspace } from "../stores/workspace";
import { api, errorText } from "../lib/api";
const store = useWorkspace(),
  message = useMessage(),
  timezone = ref("Asia/Shanghai"),
  saving = ref(false);
async function save() {
  saving.value = true;
  try {
    await api("/settings", {
      method: "PUT",
      body: JSON.stringify({ timezone: timezone.value }),
    });
    await store.refresh();
    message.success("学习时区已更新，历史计划仍保留原时区");
  } catch (e) {
    message.error(errorText(e));
  } finally {
    saving.value = false;
  }
}
onMounted(() => (timezone.value = store.settings?.timezone || "Asia/Shanghai"));
</script>
<template>
  <div class="settings-grid">
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>学习偏好</h2>
          <p>每日计划以配置时区的自然日组织</p>
        </div>
        <Globe2 :size="21" class="muted" />
      </div>
      <form @submit.prevent="save">
        <label class="form-field"
          ><span>学习时区（IANA）</span
          ><input
            v-model="timezone"
            class="text-input"
            placeholder="Asia/Shanghai"
            required
          /><small
            >例如
            Asia/Shanghai、Asia/Tokyo、America/New_York。改变时区不会产生作答或删除历史。</small
          ></label
        ><button class="btn primary" :disabled="saving">
          <Save :size="16" />保存偏好
        </button>
      </form>
    </section>
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>本地工作区</h2>
          <p>课程数据与教材原件保存在本机</p>
        </div>
        <HardDrive :size="21" class="muted" />
      </div>
      <dl class="settings-data">
        <dt>数据库目录</dt>
        <dd>{{ store.settings?.data_path }}</dd>
        <dt>教材与知识材料</dt>
        <dd>{{ store.settings?.workspace_path }}</dd>
        <dt>结构版本</dt>
        <dd>{{ store.settings?.schema_version }}</dd>
      </dl>
    </section>
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>备份与恢复</h2>
          <p>受控 CLI 完成全工作区备份，不覆盖现有数据</p>
        </div>
        <Database :size="21" class="muted" />
      </div>
      <p>先停止业务服务，在项目根目录运行：</p>
      <pre class="command-block">
.\.venv\Scripts\python.exe backend/manage.py backup --output D:\ExamPilot-backup.zip</pre>
      <p>恢复至空目录，校验版本、摘要与引用：</p>
      <pre class="command-block">
.\.venv\Scripts\python.exe backend/manage.py restore --file D:\ExamPilot-backup.zip --destination D:\ExamPilot-restored</pre>
      <p class="helper-text">
        Demo
        保证相同应用版本恢复；手工备份只能恢复到备份时间点。不会通过网页执行任意本机路径写入。
      </p>
    </section>
    <section class="panel">
      <div class="section-heading">
        <div>
          <h2>AI 与隐私边界</h2>
          <p>外部协助、本地裁判、人工发布</p>
        </div>
        <LockKeyhole :size="21" class="muted" />
      </div>
      <ul class="plain-list">
        <li>日常刷题、判题和复习无需 Codex 或网络。</li>
        <li>AI 生成由你主动在外部 Codex 发起，目标材料可能发送至所选模型。</li>
        <li>Codex 只应读取你授权的课程和章节；PDF 文本不构成可执行指令。</li>
        <li>校验通过不代表已授权发布，批准和发布独立留审计。</li>
      </ul>
    </section>
    <section class="panel full-span">
      <div class="section-heading">
        <div>
          <h2>Demo 临时规则</h2>
          <p>用于本次可运行演示，不等于正式产品决策或 SRS 基线批准</p>
        </div>
        <span class="pill warning">临时实现</span>
      </div>
      <p>{{ store.settings?.demo_policies.weakness }}</p>
      <p>{{ store.settings?.demo_policies.limits }}</p>
      <p class="helper-text">
        D-16
        使用本次任务指定的默认可配时区与0–7天同层冲刺；精确排序、复核结算、版本迁移、删除归档和备份策略见
        README 与 docs/DEMO_POLICIES.md。正式决策记录不会由代码自动改为已批准。
      </p>
    </section>
  </div>
</template>
