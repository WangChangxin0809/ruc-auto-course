<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const emit = defineEmits<{ close: [] }>()

const form = ref({
  smtpHost: 'smtp.qq.com',
  smtpPort: '587',
  smtpUsername: '',
  smtpPassword: '',
  fromAddress: '',
})
const saving = ref(false)
const msg = ref('')

async function load() {
  try {
    const r = await axios.get('/api/settings/smtp')
    form.value = r.data
  } catch (e) { /* defaults */ }
}

async function save() {
  saving.value = true
  msg.value = ''
  try {
    // 发送所有字段（含空值可清空），脱敏密码除外
    const data: Record<string, string> = {}
    for (const [k, v] of Object.entries(form.value)) {
      if (k === 'smtpPassword' && v && v.includes('****')) continue
      data[k] = v || ''
    }
    const params = new URLSearchParams(data).toString()
    await axios.put(`/api/settings/smtp?${params}`)
    msg.value = '已保存'
  } catch (e: any) {
    msg.value = '保存失败: ' + (e.response?.data?.detail || e.message)
  }
  saving.value = false
}

onMounted(load)
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="dialog">
      <button class="btn-close" @click="emit('close')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>

      <h3>SMTP 邮件设置</h3>
      <p class="subtitle">配置发件邮箱，成绩变动通知将从此邮箱发出</p>

      <div class="form-grid">
        <div class="field">
          <label>SMTP 服务器</label>
          <input v-model="form.smtpHost" placeholder="smtp.qq.com" />
        </div>
        <div class="field">
          <label>端口</label>
          <input v-model="form.smtpPort" placeholder="587" />
        </div>
        <div class="field">
          <label>发件邮箱</label>
          <input v-model="form.fromAddress" placeholder="123@qq.com" @change="form.smtpUsername = form.fromAddress" />
        </div>
        <div class="field">
          <label>登录账号</label>
          <input v-model="form.smtpUsername" placeholder="同发件邮箱" />
        </div>
        <div class="field">
          <label>授权码</label>
          <input v-model="form.smtpPassword" type="password" placeholder="QQ 邮箱授权码" />
        </div>
      </div>
      <p class="hint">QQ 邮箱：设置 → 账户 → POP3/SMTP 服务 → 生成授权码</p>

      <p v-if="msg" class="msg" :class="{ ok: msg === '已保存' }">{{ msg }}</p>

      <button class="btn-submit" :disabled="saving" @click="save">
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(15,15,35,0.5); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog { background: #fff; border-radius: 12px; padding: 28px; width: 440px; position: relative; box-shadow: 0 12px 40px rgba(0,0,0,0.15); }
.btn-close { position: absolute; top: 14px; right: 14px; background: none; color: #999; padding: 4px; border-radius: 6px; cursor: pointer; border: none; }
.btn-close:hover { color: #333; background: #f0f0f0; }
h3 { font-size: 18px; margin-bottom: 4px; }
.subtitle { font-size: 13px; color: #888; margin-bottom: 20px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; color: #666; font-weight: 500; }
.field input { padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; outline: none; }
.field input:focus { border-color: #1a5276; }
.hint { font-size: 11px; color: #aaa; margin-top: 12px; }
.msg { margin-top: 10px; font-size: 13px; color: #e74c3c; }
.msg.ok { color: #27ae60; }
.btn-submit { margin-top: 14px; width: 100%; padding: 10px; background: #1a1a35; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-submit:disabled { opacity: 0.6; }
</style>
