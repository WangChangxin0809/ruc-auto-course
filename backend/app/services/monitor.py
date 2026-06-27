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
_global_email: str = ""


def get_poll_interval() -> int:
    return _poll_interval


def set_poll_interval(seconds: int):
    global _poll_interval
    _poll_interval = seconds


def is_running() -> bool:
    return _monitor_task is not None and not _monitor_task.done()


async def _poll_student(db: Session, student: Student):
    """对单个学生执行一次轮询"""
    student_id = student.student_id

    # 每次都重新登录获取新 token（适用于长间隔轮询）
    password = decrypt_password(student.password)
    result = do_login(student_id, password)
    if not result:
        print(f"[monitor] 登录失败，跳过本轮 {student_id}")
        return
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
        print(f"[monitor] 拉取成绩失败 {student_id}")
        return

    # 同步 + 比对
    result = sync_grades(db, student, raw)
    new_count = result["new_count"]
    updated_count = result["updated_count"]

    if new_count == 0 and updated_count == 0:
        return

    print(f"[monitor] {student_id} 变化: 新增{new_count} 更新{updated_count}")

    # 记录通知日志
    grade_ids = [g.cjgl016id for g in result["new_grades"] + result["updated_grades"]]
    if new_count:
        log = NotificationLog(student_id=student_id, grade_ids=json.dumps(grade_ids), change_type="new")
        db.add(log)
    if updated_count:
        log = NotificationLog(student_id=student_id, grade_ids=json.dumps(grade_ids), change_type="updated")
        db.add(log)
    db.commit()

    # 发送邮件到学生个人邮箱
    if not student.email:
        print(f"[monitor] {student_id} 未设置通知邮箱，跳过")
        return
    student_name = student.name or student_id
    send_grade_email(student.email, student_name, result["new_grades"], result["updated_grades"])


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
    _poll_interval = poll_interval

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


def get_global_email() -> str:
    return _global_email


def set_global_email(email: str):
    global _global_email
    _global_email = email
