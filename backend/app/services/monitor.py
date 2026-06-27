"""
后台成绩监控 — asyncio 轮询循环
"""
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Student, NotificationLog, now
from .auth import do_login, decrypt_password
from .grade import fetch_grades_from_api, sync_grades, send_grade_email

TZ = timezone(timedelta(hours=8))

_monitor_task: asyncio.Task | None = None
_poll_interval: int = 30


def get_poll_interval() -> int:
    return _poll_interval


def set_poll_interval(seconds: int):
    global _poll_interval
    _poll_interval = seconds


def is_running() -> bool:
    return _monitor_task is not None and not _monitor_task.done()


def poll_student_sync(db: Session, student: Student) -> dict:
    """对单个学生执行一次轮询（同步版本，供监控和测试共用）
    返回 {"ok": bool, "new": int, "updated": int, "error": str}
    """
    student_id = student.student_id

    # 每次都重新登录获取新 token
    password = decrypt_password(student.password)
    result = do_login(student_id, password)
    if not result:
        return {"ok": False, "new": 0, "updated": 0, "error": "登录失败"}
    student.res_token = result["resToken"]
    student.session = result["session"]
    student.authcode = result["authcode"]
    student.token_expires_at = result["token_expires_at"]
    student.name = result.get("name", result["authcode"])
    student.major = result.get("major", student.major or "")
    student.grade = result.get("grade", student.grade or "")
    db.commit()

    # 拉取成绩
    raw = fetch_grades_from_api(student.res_token, student.session, student.authcode)
    if raw is None:
        return {"ok": False, "new": 0, "updated": 0, "error": "拉取成绩失败"}

    # 同步 + 比对
    sync_result = sync_grades(db, student, raw)
    new_count = sync_result["new_count"]
    updated_count = sync_result["updated_count"]

    if new_count == 0 and updated_count == 0:
        return {"ok": True, "new": 0, "updated": 0, "error": ""}

    print(f"[monitor] {student_id} 变化: 新增{new_count} 更新{updated_count}")

    # 先发送邮件，成功后再记录日志
    email_sent = False
    if student.email:
        email_sent = send_grade_email(student.email, student.name or student_id,
                                      sync_result["new_grades"], sync_result["updated_grades"])

    if email_sent:
        grade_ids = [g.cjgl016id for g in sync_result["new_grades"] + sync_result["updated_grades"]]
        if new_count:
            db.add(NotificationLog(student_id=student_id, grade_ids=json.dumps(grade_ids), change_type="new"))
        if updated_count:
            db.add(NotificationLog(student_id=student_id, grade_ids=json.dumps(grade_ids), change_type="updated"))
        db.commit()

    return {"ok": True, "new": new_count, "updated": updated_count,
            "new_grades": sync_result["new_grades"], "updated_grades": sync_result["updated_grades"]}


async def _poll_student(db: Session, student: Student):
    """异步包装：在独立线程执行同步 I/O，不阻塞事件循环"""
    import asyncio
    await asyncio.to_thread(poll_student_sync, db, student)


async def _poll_loop():
    """主轮询循环"""
    global _poll_interval
    print(f"[monitor] 轮询启动，间隔 {_poll_interval}s")
    while True:
        try:
            db = SessionLocal()
            students = db.query(Student).filter(Student.is_monitored == True).all()
            for student in students:
                try:
                    await _poll_student(db, student)
                except Exception as e:
                    print(f"[monitor] 轮询学生 {student.student_id} 异常: {e}")
            db.close()
        except Exception as e:
            print(f"[monitor] 轮询循环异常: {e}")

        await asyncio.sleep(_poll_interval)


def start_monitor(poll_interval: int = 30):
    """启动后台轮询任务"""
    global _monitor_task, _poll_interval
    _poll_interval = max(5, min(3600, poll_interval))  # 限制 5s ~ 1h

    if _monitor_task and not _monitor_task.done():
        print("[monitor] 已在运行中")
        return False

    _monitor_task = asyncio.create_task(_poll_loop())
    print("[monitor] 已启动")
    return True


def stop_monitor():
    """停止后台轮询"""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        print("[monitor] 已停止")
        return True
    return False
