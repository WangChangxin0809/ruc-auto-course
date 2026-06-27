<script setup lang="ts">
import { computed } from 'vue'
import type { GradeItem } from '../types'

const props = defineProps<{ grades: GradeItem[]; newIds: string[] }>()

const summary = computed(() => {
  const isPf = (g: GradeItem) => g.cjfscode === '3'
  const allCredits = props.grades.reduce((s, g) => s + (Number(g.credit) || 0), 0)
  const allPoints = props.grades.reduce((s, g) => s + (Number(g.grade_point) || 0), 0)
  const gpaItems = props.grades.filter(g => !isPf(g))
  const gpaCredits = gpaItems.reduce((s, g) => s + (Number(g.credit) || 0), 0)
  const gpaPoints = gpaItems.reduce((s, g) => s + (Number(g.grade_point) || 0), 0)
  const gpa = gpaCredits > 0 ? (gpaPoints / gpaCredits).toFixed(2) : '0.00'
  return { allCredits, allPoints, gpaCredits, gpaPoints, gpa, pfCount: props.grades.length - gpaItems.length }
})

const semester = computed(() => props.grades[0]?.semester || '')
</script>

<template>
  <div class="grade-section" v-if="grades.length">
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>课程名称</th>
            <th>教师</th>
            <th>课程类别</th>
            <th>课程模块</th>
            <th class="num">学分</th>
            <th class="num">平时</th>
            <th class="num">期中</th>
            <th class="num">期末</th>
            <th class="num">最终</th>
            <th class="num">绩点</th>
            <th>标志</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="g in grades"
            :key="g.cjgl016id"
            :class="{ 'row-new': newIds.includes(g.cjgl016id), 'row-pf': g.cjfscode === '3' }"
          >
            <td class="cell-name">
              <span v-if="newIds.includes(g.cjgl016id)" class="new-dot" title="新增成绩">●</span>
              {{ g.course_name }}
            </td>
            <td>{{ g.teacher }}</td>
            <td>{{ g.category }}</td>
            <td>{{ g.course_module }}</td>
            <td class="num">{{ g.credit }}</td>
            <td class="num">{{ g.daily_score }}</td>
            <td class="num">{{ g.midterm_score }}</td>
            <td class="num">{{ g.final_score }}</td>
            <td class="num cell-score">{{ g.score }}</td>
            <td class="num">{{ g.grade_point }}</td>
            <td>{{ g.grade_note }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="row-summary">
            <td :colspan="11">
              <div class="summary-content">
                <span>{{ semester }}</span>
                <span class="summary-sep">·</span>
                <span>已取得总学分 <strong>{{ summary.allCredits }}</strong></span>
                <span class="summary-sep">·</span>
                <span>总学分绩点 <strong>{{ summary.allPoints }}</strong></span>
                <span class="summary-sep">·</span>
                <span>平均学分绩点 <strong class="gpa-value">{{ summary.gpa }}</strong></span>
                <span v-if="summary.pfCount > 0" class="gpa-note">
                  （不含 {{ summary.pfCount }} 门 P/F 课程）
                </span>
              </div>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- GPA Legend -->
    <details class="gpa-legend">
      <summary>学分绩点核算方法</summary>
      <div class="legend-grid">
        <div class="legend-item"><b>A</b><span>90-100</span><em>4.0</em></div>
        <div class="legend-item"><b>A-</b><span>86-89</span><em>3.7</em></div>
        <div class="legend-item"><b>B+</b><span>83-85</span><em>3.3</em></div>
        <div class="legend-item"><b>B</b><span>80-82</span><em>3.0</em></div>
        <div class="legend-item"><b>B-</b><span>76-79</span><em>2.7</em></div>
        <div class="legend-item"><b>C+</b><span>73-75</span><em>2.3</em></div>
        <div class="legend-item"><b>C</b><span>70-72</span><em>2.0</em></div>
        <div class="legend-item"><b>C-</b><span>66-69</span><em>1.7</em></div>
        <div class="legend-item"><b>D+</b><span>63-65</span><em>1.3</em></div>
        <div class="legend-item"><b>D</b><span>60-62</span><em>1.0</em></div>
        <div class="legend-item"><b>P</b><span>考查合格</span><em>1.0</em></div>
        <div class="legend-item"><b>F</b><span>不合格</span><em>0</em></div>
      </div>
      <p class="legend-formula">每门课学分绩点 = 该课学分数 × 绩点 &nbsp;|&nbsp; GPA = 各门课程学分绩点之和 ÷ 各门课程学分数之和</p>
    </details>
  </div>

  <div v-else class="empty-box">
    <p>暂无成绩数据</p>
  </div>
</template>

<style scoped>
.grade-section {
  background: var(--white);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 1100px;
}

th {
  text-align: left;
  padding: 12px 10px;
  background: #f8f8fb;
  color: var(--ink-600);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid var(--ink-100);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}
th.num { text-align: right; }

td {
  padding: 11px 10px;
  border-bottom: 1px solid #f3f3f6;
  color: var(--ink-800);
  vertical-align: middle;
}
td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: var(--font);
}

.row-new {
  background: linear-gradient(90deg, #f0faf5 0%, #fafdfb 100%);
}
.row-pf {
  color: var(--ink-300);
}

.cell-name {
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-score {
  font-weight: 700;
  color: var(--ink-900);
  font-size: 14px;
}

.new-dot {
  color: var(--jade);
  font-size: 8px;
  margin-right: 4px;
  vertical-align: middle;
  animation: blink 1.5s ease-in-out infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Summary row */
.row-summary td {
  background: #f0f0f5;
  padding: 14px 16px;
}
.summary-content {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-800);
  flex-wrap: wrap;
}
.summary-sep { color: var(--ink-200); }
.gpa-value { color: var(--cinnabar); font-size: 16px; }
.gpa-note { font-size: 12px; color: var(--ink-300); font-weight: 400; }

/* GPA Legend */
.gpa-legend {
  padding: 0 16px 16px;
  border-top: 1px solid var(--ink-100);
}
.gpa-legend summary {
  padding: 14px 0;
  font-size: 13px;
  color: var(--ink-600);
  cursor: pointer;
  font-weight: 500;
}
.legend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 4px;
  margin-bottom: 10px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.legend-item b {
  width: 24px;
  color: var(--ink-800);
}
.legend-item span {
  color: var(--ink-300);
  flex: 1;
}
.legend-item em {
  color: var(--ink-600);
  font-style: normal;
  font-weight: 600;
}
.legend-formula {
  font-size: 12px;
  color: var(--ink-300);
  padding: 4px 8px;
}

.empty-box {
  text-align: center;
  padding: 60px;
  color: var(--ink-300);
  font-size: 15px;
}
</style>
