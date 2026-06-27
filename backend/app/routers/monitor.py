"""
监控控制路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Student, NotificationLog, MonitorLog
from ..schemas import MonitorStatus, MonitorHistoryItem, MessageResponse
from ..services.monitor import start_monitor, stop_monitor, is_running, get_poll_interval, set_poll_interval, set_heartbeat_email, get_heartbeat_email

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/status", response_model=MonitorStatus)
async def get_status(db: Session = Depends(get_db)):
    active_count = db.query(Student).filter(Student.is_monitored == True).count()
    return MonitorStatus(
        running=is_running(),
        poll_interval=get_poll_interval(),
        active_students=active_count,
    )


@router.post("/start", response_model=MessageResponse)
async def start(poll_interval: int = 30):
    ok = start_monitor(poll_interval)
    if ok:
        return MessageResponse(message=f"监控已启动，间隔 {poll_interval}s")
    return MessageResponse(message="监控已在运行中")


@router.post("/stop", response_model=MessageResponse)
async def stop():
    ok = stop_monitor()
    if ok:
        return MessageResponse(message="监控已停止")
    return MessageResponse(message="监控未在运行")


@router.get("/config", response_model=dict)
async def get_config():
    return {"pollInterval": get_poll_interval(), "heartbeatEmail": get_heartbeat_email()}


@router.post("/config", response_model=MessageResponse)
async def set_config(poll_interval: int = 0, heartbeat_email: str = ""):
    if poll_interval > 0:
        set_poll_interval(poll_interval)
    if heartbeat_email:
        set_heartbeat_email(heartbeat_email)
    parts = []
    if poll_interval > 0:
        parts.append(f"轮询: {poll_interval}s")
    if heartbeat_email:
        parts.append(f"心跳邮箱: {heartbeat_email}")
    return MessageResponse(message="已更新: " + ", ".join(parts))


@router.get("/history", response_model=list[MonitorHistoryItem])
def get_history(db: Session = Depends(get_db)):
    logs = db.query(NotificationLog).order_by(NotificationLog.sent_at.desc()).limit(100).all()
    return [
        MonitorHistoryItem(
            id=log.id,
            student_id=log.student_id,
            change_type=log.change_type,
            grade_ids=log.get_grade_ids(),
            sent_at=log.sent_at,
        )
        for log in logs
    ]


@router.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(MonitorLog).order_by(MonitorLog.id.desc()).limit(50).all()
    return [{"id": l.id, "student_id": l.student_id, "status": l.status,
             "message": l.message, "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in logs]
