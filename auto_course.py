#!/usr/bin/env python3
"""
人大暑期学校自动选课脚本 (Inner路径: dicStuType=1 校内学生)

每 30 秒轮询可选课程，发现有余额的课程后按检查链执行选课。
每轮自动重载 config.json → 改 blacklist/targets 无需重启。

特性:
  - 多候选遍历: 按 targets优先级→剩余名额 排序，逐个尝试直到成功
  - 时间冲突自动黑名单: checkCourseSettleTime 失败 → 自动写入 config.json
  - 短路检查链: 任一步失败立即中止，减少无效请求
  - 网络异常保护: try/except 防止单次超时挂掉

正确调用链 (7步检查 + 1步选课):
  checkContactInfo -> cheCourseTimeContr -> checkCourseSelected
  -> checkCourseSurplusCapacity -> checkCourseSettleTime
  -> checkStuLabel -> getStuCourseNum -> selectCourse/selectCourseByInner

Content-Type:
  - 查询/信息类:  application/json
  - 课程操作类:  text/plain (body = 纯 id 字符串)
"""
import json
import requests
import sys
import time
import os
from datetime import datetime, timezone, timedelta

# 确保 stdout 使用 UTF-8 (Windows 下 GBK 会导致中文乱码)
# sys.stdout.reconfigure 从 Python 3.7 起可用，但 Pylance stub 不识别
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# ========== 日志双写 (屏幕 + 文件) ==========
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_course.log")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class Tee:
    def __init__(self, file_path):
        self.file = open(file_path, "a", encoding="utf-8", buffering=1)
        self.stdout = sys.stdout

    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)

    def flush(self):
        self.file.flush()
        self.stdout.flush()


sys.stdout = Tee(LOG_FILE)
sys.stderr = sys.stdout

# ========== 基础常量 ==========
TZ = timezone(timedelta(hours=8))


def ts():
    return datetime.now(TZ).strftime("%H:%M:%S")


def load_config():
    """每轮重载 — 改 blacklist/targets 无需重启"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 初始加载
cfg = load_config()
BASE_URL = cfg["baseUrl"]
TOKEN = cfg["auth"]["token"]
COOKIE = cfg["auth"]["cookie"]
APIS = cfg["apis"]

JSON_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Referer": f"{BASE_URL}/Minjw/",
}

TEXT_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "text/plain",
    "Referer": f"{BASE_URL}/Minjw/",
}


def post_json(path, data=None):
    """JSON 请求，带网络异常保护"""
    url = f"{BASE_URL}{path}"
    if data is None:
        data = {}
    try:
        return requests.post(url, headers=JSON_HEADERS, json=data, timeout=10)
    except requests.RequestException as e:
        print(f"\n  [网络异常] POST JSON 失败: {e}")
        return None


def post_text(path, body):
    """Text 请求，带网络异常保护"""
    url = f"{BASE_URL}{path}"
    try:
        return requests.post(url, headers=TEXT_HEADERS, data=body.encode("utf-8"), timeout=10)
    except requests.RequestException as e:
        print(f"\n  [网络异常] POST TEXT 失败: {e}")
        return None


def ok(resp):
    """判断响应是否成功，兼容 None。失败时提取 message 字段"""
    if resp is None:
        print(f"       [ERROR] 无服务器响应")
        return False
    symbol = "OK" if resp.status_code == 200 else "FAIL"
    msg = ""
    if resp.status_code != 200:
        try:
            data = resp.json()
            if isinstance(data, dict) and "message" in data:
                msg = f" | {data['message']}"
        except Exception:
            pass
    print(f"       [{resp.status_code}] {symbol}{msg}")
    return resp.status_code == 200


def check_chain(crs_id):
    """7步检查链 — 短路: 任一步失败立即中止。
    返回 (passed: bool, is_conflict: bool)"""
    steps = [
        ("checkContactInfo",           lambda: post_json(APIS["checkContactInfo"])),
        ("cheCourseTimeContr",         lambda: post_text(APIS["cheCourseTimeContr"], crs_id)),
        ("checkCourseSelected",        lambda: post_text(APIS["checkCourseSelected"], crs_id)),
        ("checkCourseSurplusCapacity", lambda: post_text(APIS["checkCourseSurplusCapacity"], crs_id)),
        ("checkCourseSettleTime",      lambda: post_text(APIS["checkCourseSettleTime"], crs_id)),
        ("checkStuLabel",              lambda: post_json(APIS["checkStuLabel"])),
        ("getStuCourseNum",            lambda: post_json(APIS["getStuCourseNum"])),
    ]

    for name, fn in steps:
        print(f"       {name}...", end=" ")
        resp = fn()
        if not ok(resp):
            print(f"       >>> 检查链在 [{name}] 处断开，停止后续检查。")
            return (False, name == "checkCourseSettleTime")
    return (True, False)


def do_select(crs_id, class_no, name):
    """[8/8] 执行选课: 先 selectCourseByInner, 任何非200则 fallback selectCourse"""
    print(f"\n    [8/8] 执行选课 -> {crs_id}")

    resp = post_text(APIS["selectCourseByInner"], crs_id)
    if resp and resp.status_code == 200:
        print(f"    >>> 选课成功! [{class_no}] {name}")
        return True

    code = resp.status_code if resp else "N/A"
    print(f"    selectCourseByInner -> {code}, fallback selectCourse...")

    resp = post_text(APIS["selectCourse"], crs_id)
    if resp and resp.status_code == 200:
        print(f"    >>> 选课成功! [{class_no}] {name}")
        return True

    ok(resp)
    return False


def do_drop(crs_stu_id, class_no, name):
    """退课: deleteStuCourseInfo (text/plain + crs_stu_id, 不是 crs_id!)"""
    print(f"    退课 -> [{class_no}] crs_stu_id={crs_stu_id}")
    resp = post_text(APIS["deleteStuCourseInfo"], crs_stu_id)
    if resp and resp.status_code == 200:
        print(f"    >>> 退课成功! [{class_no}] {name}")
        return True
    ok(resp)
    return False


# ========== 主循环 ==========
print("=" * 60)
print("人大暑期学校自动选课 — 轮询模式 (每 30 秒)")
print(f"启动时间: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"每轮自动重载 {CONFIG_FILE} — 改 blacklist/targets 无需重启")
print(f"时间冲突的课程会自动加入黑名单")
print("=" * 60)

round_num = 0
while True:
    round_num += 1

    # ── 每轮重载 config (blacklist / targets 热更新) ──
    cfg = load_config()
    blacklist = set(cfg.get("blacklist", []))
    targets = cfg.get("targets", [])

    print(f"\n{'─' * 40}")
    print(f"[{ts()}] 第 {round_num} 轮  blacklist={sorted(blacklist)}")

    # ── 1. 当前已选 ──
    resp = post_json(APIS["queryStuCourseOfferList"], {
        "page": {"pageIndex": 1, "pageSize": 50,
                 "orderBy": '[{ "field": "class_no", "sortType": "asc"}]'}
    })

    enrolled_count = 0
    enrolled_crs_ids = set()
    enrolled_info = {}  # class_no -> {crs_id, crs_stu_id, name}

    if resp and resp.status_code == 200:
        data = resp.json()
        for c in data.get("items", []):
            enrolled_crs_ids.add(c["crs_id"])
            enrolled_info[c["class_no"]] = {
                "crs_id": c["crs_id"],
                "crs_stu_id": c["crs_stu_id"],
                "name": c["course_name_chinese"],
            }
            enrolled_count += 1
        enrolled_str = ", ".join(
            f"[{c['class_no']}] {c['course_name_chinese']}"
            for c in data.get("items", [])
        )
        print(f"  已选 ({enrolled_count}门): {enrolled_str if enrolled_str else '(无)'}")
    else:
        print(f"  查询已选课程失败（服务器可能繁忙）")

    # ── 2. 可选课程 (全部) ──
    resp = post_json(APIS["queryCourseOfferList"], {
        "page": {"pageIndex": 1, "pageSize": 100,
                 "orderBy": '[{ "field": "class_no", "sortType": "asc"}]'}
    })

    if not resp or resp.status_code != 200:
        print(f"  查询可选课程列表失败，等待 30 秒...")
        time.sleep(30)
        continue

    all_courses = resp.json().get("items", [])

    # 有余额 + 未选过 + 不在黑名单
    candidates = [
        c for c in all_courses
        if c.get("surplus_capacity", 0) > 0
        and c["crs_id"] not in enrolled_crs_ids
        and c.get("class_no", "") not in blacklist
    ]
    print(f"  可选课程: {len(all_courses)} 门 | 有余额且未选: {len(candidates)} 门")

    if candidates:
        print(f"  >>> 候选课程 ({len(candidates)}门):")
        for c in candidates:
            print(f"      [{c['class_no']}] {c['course_name_chinese']}"
                  f" | {c.get('academy_name_chinese', '?')}"
                  f" | 剩{c['surplus_capacity']}人"
                  f" | crs_id={c['crs_id']}")

    if not candidates:
        print(f"  无候选课程，{ts()} 等待 30 秒...")
        time.sleep(30)
        continue

    # ── 3. 已满则跳过 ──
    if enrolled_count >= 2:
        print(f"  已选 {enrolled_count} 门 (上限 2)，需手动退课才能选新课")
        print(f"  {ts()} 等待 30 秒...")
        time.sleep(30)
        continue

    # ── 4. 排序: targets优先 → 按名额倒序 ──
    target_index = {t: i for i, t in enumerate(targets)}
    candidates.sort(key=lambda c: (
        target_index.get(c["class_no"], 999),
        -c.get("surplus_capacity", 0)
    ))

    # ── 5. 遍历所有候选，逐个尝试 ──
    selected = False
    for target in candidates:
        crs_id = target["crs_id"]
        class_no = target["class_no"]
        course_name = target["course_name_chinese"]

        print(f"\n  尝试: [{class_no}] {course_name}")
        print(f"  crs_id: {crs_id} | 剩余名额: {target.get('surplus_capacity')}")

        print(f"  === 检查链 ===")
        passed, is_conflict = check_chain(crs_id)
        if not passed:
            if is_conflict:
                print(f"  >>> [{class_no}] 时间冲突，自动加入黑名单!")
                cfg = load_config()
                bl = set(cfg.get("blacklist", []))
                bl.add(class_no)
                cfg["blacklist"] = sorted(bl)
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
            else:
                print(f"  [{class_no}] 检查未通过，尝试下一个候选...")
            continue

        success = do_select(crs_id, class_no, course_name)
        if success:
            print(f"  选课成功! [{class_no}] {course_name}")
            selected = True
            break
        else:
            print(f"  [{class_no}] 选课提交未成功，尝试下一个候选...")

    if not selected:
        print(f"  所有候选均失败，{ts()} 等待 30 秒...")

    print(f"  {ts()} 继续监听...")
    time.sleep(30)
