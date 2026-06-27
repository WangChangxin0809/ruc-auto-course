import axios from 'axios'
import type {
  Student,
  StudentCreate,
  GradeItem,
  GradeRefreshResult,
  MonitorStatus,
  MonitorHistoryItem,
} from '../types'

const api = axios.create({ baseURL: '/api' })

// Students
export const addStudent = (data: StudentCreate) =>
  api.post<Student>('/students/', data).then(r => r.data)

export const listStudents = () =>
  api.get<Student[]>('/students/').then(r => r.data)

export const getStudent = (id: string) =>
  api.get<Student>(`/students/${id}`).then(r => r.data)

export const deleteStudent = (id: string) =>
  api.delete(`/students/${id}`).then(r => r.data)

export const reloginStudent = (id: string) =>
  api.post(`/students/${id}/relogin`).then(r => r.data)

export const toggleMonitorStudent = (id: string) =>
  api.post<Student>(`/students/${id}/monitor`).then(r => r.data)

export const testEmailStudent = (id: string) =>
  api.post(`/students/${id}/test-email`).then(r => r.data)

export const updateStudentEmail = (id: string, email: string) =>
  api.put<Student>(`/students/${id}/email?email=${encodeURIComponent(email)}`).then(r => r.data)


// Grades
export const getGrades = (studentId: string) =>
  api.get<GradeItem[]>(`/grades/${studentId}`).then(r => r.data)

export const refreshGrades = (studentId: string) =>
  api.post<GradeRefreshResult>(`/grades/${studentId}/refresh`).then(r => r.data)

// Monitor
export const getMonitorStatus = () =>
  api.get<MonitorStatus>('/monitor/status').then(r => r.data)

export const startMonitor = (interval = 30) =>
  api.post(`/monitor/start?poll_interval=${interval}`).then(r => r.data)

export const stopMonitor = () =>
  api.post('/monitor/stop').then(r => r.data)

export const getMonitorHistory = () =>
  api.get<MonitorHistoryItem[]>('/monitor/history').then(r => r.data)
