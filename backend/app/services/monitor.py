"""
后台成绩监控 — asyncio 轮询循环
"""
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Student, NotificationLog, MonitorLog, now
from .auth import do_login, decrypt_password
from .grade import fetch_grades_from_api, sync_grades, send_grade_email, EMAIL_CONFIG

TZ = timezone(timedelta(hours=8))

_monitor_task: asyncio.Task | None = None
_heartbeat_task: asyncio.Task | None = None
_poll_interval: int = 30
_heartbeat_interval: int = 5 * 3600  # 5 小时
_heartbeat_email: str = ""


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

    def _log(status: str, msg: str):
        db.add(MonitorLog(student_id=student_id, status=status, message=msg))
        db.commit()
        # 只保留最近 200 条
        old = db.query(MonitorLog).order_by(MonitorLog.id.desc()).offset(200).all()
        for o in old:
            db.delete(o)
        db.commit()

    _log("ok", "开始轮询")

    # 每次都重新登录获取新 token
    password = decrypt_password(student.password)
    result = do_login(student_id, password)
    if not result:
        _log("fail", "登录失败")
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
        _log("fail", "拉取成绩失败")
        return {"ok": False, "new": 0, "updated": 0, "error": "拉取成绩失败"}

    # 同步 + 比对
    sync_result = sync_grades(db, student, raw)
    new_count = sync_result["new_count"]
    updated_count = sync_result["updated_count"]

    if new_count == 0 and updated_count == 0:
        _log("noop", f"无变化 ({sync_result['total']}门)")
        return {"ok": True, "new": 0, "updated": 0, "error": ""}

    print(f"[monitor] {student_id} 变化: 新增{new_count} 更新{updated_count}")
    _log("ok", f"新增{new_count}门 更新{updated_count}门 (共{sync_result['total']}门)")

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


async def _heartbeat_loop():
    """心跳检测：每 5 小时发送监控总结邮件"""
    global _heartbeat_interval, _heartbeat_email
    await asyncio.sleep(60)  # 启动后等 1 分钟再发第一次
    while True:
        try:
            db = SessionLocal()
            students = db.query(Student).filter(Student.is_monitored == True).all()
            if students and _heartbeat_email:
                now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
                rows_text = ""
                total_polls = 0
                for s in students:
                    from ..models import Grade as G
                    grade_count = db.query(G).filter(G.student_id == s.student_id).count()
                    poll_count = db.query(MonitorLog).filter(MonitorLog.student_id == s.student_id, MonitorLog.status == "noop").count()
                    poll_count += db.query(MonitorLog).filter(MonitorLog.student_id == s.student_id, MonitorLog.status == "ok").count()
                    last_poll = db.query(MonitorLog).filter(MonitorLog.student_id == s.student_id).order_by(MonitorLog.id.desc()).first()
                    last_poll_time = last_poll.created_at.strftime("%m/%d %H:%M") if last_poll and last_poll.created_at else "-"
                    last_g = db.query(G).filter(G.student_id == s.student_id).order_by(G.last_updated_at.desc()).first()
                    last_change = last_g.last_updated_at.strftime("%m/%d %H:%M") if last_g and last_g.last_updated_at else "-"
                    total_polls += poll_count
                    rows_text += f"""{s.name or s.student_id} ({s.student_id}) | 成绩:{grade_count}门 | 轮询:{poll_count}次 | 最近:{last_poll_time} | 变动:{last_change}\n"""
                body = f"""RUC Helper 监控心跳 — {now_str}

监控间隔: {_poll_interval}s | 学生: {len(students)}人 | 累计轮询: {total_polls}次

{rows_text}
---
此邮件由 RUC Helper 自动发送，每 5 小时一次"""
                from email.mime.text import MIMEText
                msg = MIMEText(body, "plain", "utf-8")
                msg["From"] = EMAIL_CONFIG["fromAddress"]
                msg["To"] = _heartbeat_email
                msg["Subject"] = f"[RUC Helper] 监控心跳 — {now_str}"
                import smtplib
                server = smtplib.SMTP(EMAIL_CONFIG["smtpHost"], EMAIL_CONFIG["smtpPort"], timeout=15)
                server.starttls()
                server.login(EMAIL_CONFIG["smtpUsername"], EMAIL_CONFIG["smtpPassword"])
                server.sendmail(EMAIL_CONFIG["fromAddress"], [_heartbeat_email], msg.as_string())
                server.quit()
                print(f"[heartbeat] 已发送至 {_heartbeat_email}")
            db.close()
        except Exception as e:
            print(f"[heartbeat] 异常: {e}")
        await asyncio.sleep(_heartbeat_interval)


def set_heartbeat_email(email: str):
    global _heartbeat_email
    _heartbeat_email = email


def get_heartbeat_email() -> str:
    return _heartbeat_email


def start_monitor(poll_interval: int = 30):
    global _monitor_task, _heartbeat_task, _poll_interval
    _poll_interval = max(5, min(3600, poll_interval))

    if _monitor_task and not _monitor_task.done():
        print("[monitor] 已在运行中")
        return False

    _monitor_task = asyncio.create_task(_poll_loop())
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    print("[monitor] 已启动 (含心跳)")
    return True


def stop_monitor():
    global _monitor_task, _heartbeat_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
    if _heartbeat_task and not _heartbeat_task.done():
        _heartbeat_task.cancel()
    print("[monitor] 已停止")
    return (_monitor_task is not None) or (_heartbeat_task is not None)
