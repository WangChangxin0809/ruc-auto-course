# RUC Auto Choose Course

人大教务系统自动选课脚本 — 用于[人大国际小学期](https://jw.ruc.edu.cn)（RUC International Summer School）的课程自动抢课。

每 2 秒轮询可选课程列表，发现有余量的目标课程后自动执行 7 步检查链 + 选课，支持热重载配置（改黑名单/目标课程无需重启）。

## 功能

- **自动抢课** — 30 秒轮询，发现空位立即抢
- **热重载配置** — 修改 `config.json` 的黑名单、目标课程，脚本自动感知
- **短路检查链** — 7 步前置检查，任一步失败即跳过，减少无效请求
- **多候选遍历** — 同时有多个候选课程时，按优先级逐个尝试直到成功
- **时间冲突自动黑名单** — 和已选课时间冲突的课程自动加入黑名单
- **Inner/Outer 双路径** — 校内 IP 走 `selectCourseByInner`，失败自动 fallback `selectCourse`
- **日志双写** — 屏幕 + `auto_course.log` 文件同步输出

## 快速开始

### 1. 环境

```bash
pip install uv          # 如果没有 uv
uv sync                 # 自动创建 venv + 安装依赖
```

Python 3.8+ + `uv` + `requests`。也可以用传统 `pip install -r requirements.txt`。

### 2. 获取凭据

1. 浏览器打开 [https://jw.ruc.edu.cn](https://jw.ruc.edu.cn)，用学号+密码登录
2. 按 `F12` 打开开发者工具 → **Application**（应用程序）
3. 左侧 `Storage → Cookies → https://jw.ruc.edu.cn`
4. 找到 `EL-ADMIN-TOEKN`，复制它的值（这就是 JWT Token）
5. 复制完整的 Cookie 行（包含 `access_token`、`SESSION`、`EL-ADMIN-TOEKN`）

> ⚠️ JWT 有效期约 4 小时，过期需重新获取。也可以直接在 Network 面板抓任意 API 请求的 `Authorization` header 和 `Cookie`。

### 3. 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`，填入真实凭据：

```json
{
  "baseUrl": "https://jw.ruc.edu.cn",
  "auth": {
    "token": "你的_EL-ADMIN-TOEKN_值",
    "cookie": "access_token=xxx; SESSION=xxx; EL-ADMIN-TOEKN=xxx"
  }
}
```

### 4. 运行

```bash
uv run auto_course.py
# 或
python auto_course.py
```

## 配置说明

`config.json` 中可热修改的字段（无需重启）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `blacklist` | `string[]` | 永不选的课程班号，如 `["FD2643", "CM2601"]` |
| `targets` | `string[]` | 优先抢的课程（按顺序），空 = 按名额排序抢 |

改完保存，最多 2 秒后脚本自动生效。

## 工作原理

### 选课检查链（7 + 1 步）

```
checkContactInfo          → 检查联系方式
cheCourseTimeContr        → 检查选课时间 + 数量上限
checkCourseSelected       → 检查是否已选过
checkCourseSurplusCapacity → 检查剩余名额
checkCourseSettleTime     → 检查时间冲突（失败自动加黑名单）
checkStuLabel             → 检查学生标签
getStuCourseNum           → 获取已选门数
────────────────────────────────────
selectCourseByInner       → 校内选课 (Inner路径)
  └─ 403 fallback → selectCourse → 外网选课
```

### Content-Type 规范

| 接口类型 | Content-Type | Body |
|----------|-------------|------|
| 查询类 | `application/json` | `{"page": {...}}` |
| 操作类（选课/退课/检查） | **`text/plain`** | 纯 `crs_id` 字符串 |

> ⚠️ 关键坑点：操作类接口必须用 `text/plain` 传纯字符串，用 `application/json` 会返回 400。

### 选课时间窗口

学期数据中包含三轮校内选课时间（`internalCourseStartTime` / `internalCourseEndTime`，后缀 `2`、`3` 表示轮次），脚本通过 `checkSelectCourseTime` 和 `checkCourseSettleTime` 验证。

## 文件结构

```
├── auto_course.py          # 主脚本
├── pyproject.toml          # uv 项目配置
├── requirements.txt        # pip 兼容
├── config.example.json     # 配置模板（可提交）
├── config.json             # 真实凭据（gitignore 保护）
├── .gitignore
├── CONTEXT.md              # 开发笔记 / API 分析记录
└── auto_course.log         # 运行日志（gitignore 保护）
```

## 系统信息

- **系统**: 人大国际小学期 (RUC ISS)
- **开发商**: 湖南强智科技
- **前端**: Vue.js SPA (Element UI)
- **网关**: `jw.ruc.edu.cn` → `gateway-service:8001`
- **认证**: 学号+密码+验证码登录 → `EL-ADMIN-TOEKN` (JWT) + Cookie

## 免责声明

本工具仅供学习研究使用。请遵守学校相关规定，合理使用选课系统资源。

## License

MIT
