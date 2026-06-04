# Auto Choose Course — 人大教务系统自动选课

## 项目目标
自动选课脚本，用于人大暑期学校（jw.ruc.edu.cn）的课程选择和退课操作。

## 系统信息
- **系统**: 人大国际小学期 (RUC ISS)
- **开发商**: 湖南强智科技
- **网关**: `https://jw.ruc.edu.cn` → `gateway-service:8001`
- **前端**: Vue.js SPA (Element UI)

---

## API 架构（已验证）

### 鉴权
- `Authorization: Bearer <JWT>` + Cookie
- JWT 有效期约 4 小时，过期需重新登录

### 两套 Content-Type

| 接口类型 | Content-Type | Body 格式 |
|----------|-------------|-----------|
| 查询类 (列表、信息) | `application/json` | `{"page": {...}}` 或 `{}` |
| 操作类 (选课、退课、检查) | **`text/plain`** | 纯字符串 |

### 已确认可用的 API

| 端点 | 用途 | Content-Type | Body |
|------|------|-------------|------|
| `/qsmart/common/sessionUserInfo` (GET) | 用户信息 | - | - |
| `/minJwxt/mgmt/public/service/querySemesterListBySelect` (POST) | 学期列表 | JSON | `{}` |
| `/minJwxt/mgmt/student/course/getStuInfo` (POST) | 学生信息 | JSON | `{}` |
| `/minJwxt/mgmt/student/course/checkSelectCourseTime` (POST) | 检查选课时间 | JSON | `{}` |
| `/minJwxt/mgmt/student/course/queryCourseOfferListByPage` (POST) | 可选课程列表 | JSON | `{"page": {...}}` |
| `/minJwxt/mgmt/student/course/queryStuCourseOfferListByPage` (POST) | 已选课程列表 | JSON | `{"page": {...}}` |
| `/minJwxt/mgmt/student/course/selectCourse` (POST) | **选课** | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/selectCourseByInner` (POST) | **校内选课** | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/deleteStuCourseInfo` (POST) | **退课** | **text/plain** | **`crs_stu_id`** |
| `/minJwxt/mgmt/student/course/cancelSelectCourse` (POST) | 退课(废弃) | text/plain | ❌ 403 |
| `/minJwxt/mgmt/student/course/checkCourseSurplusCapacity` (POST) | 检查剩余名额 | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/checkCourseSettleTime` (POST) | 检查时间冲突 | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/selectCourseCheckForConflicts` (POST) | 冲突检查 | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/checkCourseSelected` (POST) | 检查是否已选 | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/checkContactInfo` (POST) | 联系信息检查 | JSON | `{}` |
| `/minJwxt/mgmt/student/course/checkStuLabel` (POST) | 学生标签检查 | JSON | `{}` |
| `/minJwxt/mgmt/student/course/cheCourseTimeContr` (POST) | 时间+数量校验 | **text/plain** | `crs_id` |
| `/minJwxt/mgmt/student/course/getStuCourseNum` (POST) | 已选门数 | JSON | `{}` |

### 退课接口

| 接口 | Content-Type | Body | 状态 |
|------|-------------|------|------|
| `deleteStuCourseInfo` | **`text/plain`** | **`crs_stu_id`** | ✅ **200 OK** |
| `cancelSelectCourse` | `text/plain` | `crs_id` | ❌ 403 Forbidden |

> **关键**: `deleteStuCourseInfo` 的 body 是 `crs_stu_id`（不是 `crs_id`！）
> 两个 id 都是 32 字符，浏览器抓包无法区分，实测确认是 `crs_stu_id`。
> 之前错误地用了 `crs_id`，导致 400 "Cannot be cancelled!"。

### 请求格式示例

**选课** (text/plain, body = crs_id):
```
8a74591a9b13548c019b2101c646007a
```

**退课** (text/plain, body = crs_stu_id):
```
8a7476069e8e9760019e923d699c00a8
```

---

## 选课时间窗口

学期数据中包含三轮校内选课时间戳（北京时间）:

| 轮次 | 字段名 | 开始 | 结束 |
|------|--------|------|------|
| 第1轮 | `internalCourseStartTime` / `internalCourseEndTime` | 05-28 00:00 | 06-03 00:00 |
| 第2轮 | `internalCourseStartTime2` / `internalCourseEndTime2` | 06-03 00:00 | 06-05 00:00 |
| 第3轮 | `internalCourseStartTime3` / `internalCourseEndTime3` | 07-06 00:00 | 07-24 00:00 |
| 校外选课 | `externalCourseStartTime` / `externalCourseEndTime` | 03-01 00:00 | 05-27 00:00 |

---

## 已解决问题

### 1. Content-Type 错误
选课/退课/检查类接口要求 `Content-Type: text/plain`。之前错误地使用 `application/json` 导致 400。

### 2. deleteStuCourseInfo 退课成功
- Content-Type: `text/plain`
- Body: 纯 `crs_stu_id` 字符串（32字符，从已选课程列表获取）
- **不是** `crs_id`！**不是** JSON！

### 3. 选课调用链验证
8 步检查链全部通过 → `selectCourseByInner` 403 → fallback `selectCourse` 200 OK，成功选课。
- 最多选 2 门，满额后需先退再选
- 时间冲突会被 `checkCourseSettleTime` 拦截

---

## 重要警示
⚠️ `config.json` 包含真实凭据 (JWT + Cookie)，**不要提交到 git**。
已通过 `.gitignore` 排除。

## 文件说明
- `config.json` — 凭据和 API 端点清单（gitignore）
- `auto_course.py` — 自动选课脚本（轮询 + 检查链 + 选课）
- `CONTEXT.md` — 本文档 (API 分析笔记)
