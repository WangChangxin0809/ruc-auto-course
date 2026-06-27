<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listStudents, deleteStudent, getMonitorStatus, startMonitor, stopMonitor, toggleMonitorStudent, testEmailStudent, setMonitorConfig } from '../api'
import type { Student, MonitorStatus } from '../types'
import StudentCard from '../components/StudentCard.vue'
import AddStudentDialog from '../components/AddStudentDialog.vue'
import SmtpSettings from '../components/SmtpSettings.vue'

const students = ref<Student[]>([])
const status = ref<MonitorStatus>({ running: false, poll_interval: 30, active_students: 0 })
const showAdd = ref(false)
const showSettings = ref(false)
const loading = ref(true)
const pollInterval = ref(30)

async function load() {
  loading.value = true
  try {
    const [s, st] = await Promise.all([listStudents(), getMonitorStatus()])
    students.value = s
    status.value = st
    pollInterval.value = st.poll_interval || 30
  } catch (e) {
    console.error(e)
    students.value = []
  }
  loading.value = false
}

async function toggleMonitor() {
  if (status.value.running) {
    await stopMonitor()
  } else {
    await setMonitorConfig('', pollInterval.value)
    await startMonitor(pollInterval.value)
  }
  const st = await getMonitorStatus()
  status.value = st
}

async function handleTestEmail(studentId: string) {
  try {
    const r = await testEmailStudent(studentId) as any
    alert(r.message || '测试邮件已发送')
  } catch (e: any) {
    alert(e.response?.data?.detail || '发送失败')
  }
}

async function handleToggleStudent(studentId: string) {
  const updated = await toggleMonitorStudent(studentId)
  const idx = students.value.findIndex(s => s.student_id === studentId)
  if (idx >= 0) students.value[idx] = updated
  const st = await getMonitorStatus()
  status.value = st
}

async function removeStudent(id: string) {
  if (!confirm('确定删除该学生？此操作不可恢复。')) return
  try {
    await deleteStudent(id)
    await load()
  } catch (e: any) {
    alert('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function onAdded() {
  showAdd.value = false
  load()
}

onMounted(load)
</script>

<template>
  <div class="dashboard">
    <!-- Top Navigation -->
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <span class="brand-icon">◈</span>
          <h1>RUC 成绩监控</h1>
        </div>

        <div class="topbar-controls">
          <div class="interval-group">
            <span class="interval-label">轮询间隔</span>
            <input v-model.number="pollInterval" type="number" min="5" max="3600" class="interval-input" />
            <span class="interval-unit">秒</span>
          </div>

          <div class="monitor-group">
            <span class="pulse" :class="{ live: status.running }"></span>
            <span class="monitor-label">{{ status.running ? '监控中' : '已停止' }}</span>
            <span class="monitor-count">{{ status.active_students }}人</span>
            <button
              @click="toggleMonitor"
              :class="status.running ? 'btn-stop' : 'btn-start'"
            >
              {{ status.running ? '停止监控' : '启动监控' }}
            </button>
          </div>

          <button class="btn-settings" @click="showSettings = true" title="SMTP 设置">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          </button>
          <button class="btn-add" @click="showAdd = true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            添加学生
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <div v-if="loading" class="state-box">
        <div class="spinner"></div>
        <p>加载中...</p>
      </div>

      <div v-else-if="students.length === 0" class="state-box empty-state">
        <div class="empty-icon">◈</div>
        <h3>暂无学生</h3>
        <p>点击右上角「添加学生」开始监控成绩变化</p>
      </div>

      <div v-else class="card-grid">
        <StudentCard
          v-for="s in students"
          :key="s.student_id"
          :student="s"
          @toggleMonitor="handleToggleStudent(s.student_id)"
          @testEmail="handleTestEmail(s.student_id)"
          @delete="removeStudent(s.student_id)"
        />
      </div>
    </main>

    <AddStudentDialog v-if="showAdd" @close="showAdd = false" @added="onAdded" />
    <SmtpSettings v-if="showSettings" @close="showSettings = false" />
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: var(--paper);
}

/* ── Top Bar ── */
.topbar {
  background: var(--ink-900);
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 2px 20px rgba(15, 15, 35, 0.3);
}
.topbar-inner {
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 28px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.brand-icon {
  font-size: 22px;
  color: var(--gold);
}
.brand h1 {
  font-size: 17px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.5px;
}

.topbar-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* Interval input */
.interval-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.interval-label {
  font-size: 12px;
  color: var(--ink-300);
}
.interval-input {
  width: 50px;
  height: 28px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  color: #fff;
  text-align: center;
  font-size: 13px;
}
.interval-unit {
  font-size: 12px;
  color: var(--ink-300);
}

/* Monitor group */
.monitor-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-300);
  flex-shrink: 0;
}
.pulse.live {
  background: var(--jade);
  box-shadow: 0 0 8px var(--jade);
  animation: pulse-ring 2s infinite;
}
@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 4px var(--jade); }
  50% { box-shadow: 0 0 14px var(--jade); }
}
.monitor-label {
  font-size: 13px;
  color: #ccc;
}
.monitor-count {
  font-size: 12px;
  color: var(--ink-300);
}

.btn-start, .btn-stop, .btn-add {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}
.btn-start {
  background: var(--jade);
  color: #fff;
}
.btn-start:hover { background: #16704f; }
.btn-stop {
  background: var(--cinnabar);
  color: #fff;
}
.btn-stop:hover { background: #a01830; }
.btn-add {
  background: rgba(255,255,255,0.12);
  color: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-add:hover { background: rgba(255,255,255,0.22); }

/* ── Main Content ── */
.main-content {
  max-width: 1320px;
  margin: 0 auto;
  padding: 32px 28px;
}

.state-box {
  text-align: center;
  padding: 80px 20px;
  color: var(--ink-300);
}

.empty-icon {
  font-size: 48px;
  color: var(--ink-200);
  margin-bottom: 16px;
}
.empty-state h3 {
  font-size: 18px;
  color: var(--ink-600);
  margin-bottom: 8px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--ink-100);
  border-top-color: var(--ink-600);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
