"""
全局设置路由 — SMTP 配置等
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Setting
from ..services.grade import reload_email_config

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SMTP = {
    "smtpHost": "smtp.qq.com",
    "smtpPort": "587",
    "smtpUsername": "",
    "smtpPassword": "",
    "fromAddress": "",
}


@router.get("/smtp")
def get_smtp(db: Session = Depends(get_db)):
    result = {}
    for k, default in DEFAULT_SMTP.items():
        s = db.query(Setting).filter(Setting.key == k).first()
        val = s.value if s else default
        # 密码脱敏
        if k == "smtpPassword" and val:
            val = val[:2] + "****" + val[-2:] if len(val) > 4 else "****"
        result[k] = val
    return result


@router.put("/smtp")
def set_smtp(
    smtpHost: str = "",
    smtpPort: str = "",
    smtpUsername: str = "",
    smtpPassword: str = "",
    fromAddress: str = "",
    db: Session = Depends(get_db),
):
    updates = {
        "smtpHost": smtpHost,
        "smtpPort": smtpPort,
        "smtpUsername": smtpUsername,
        "smtpPassword": smtpPassword,
        "fromAddress": fromAddress,
    }
    for k, v in updates.items():
        # 跳过脱敏占位符，避免覆盖真实密码
        if k == "smtpPassword" and v and "****" in v:
            continue
        s = db.query(Setting).filter(Setting.key == k).first()
        if s:
            s.value = v
        elif v:  # 空值不创建新记录
            db.add(Setting(key=k, value=v))
    db.commit()
    reload_email_config()
    masked = {k: (v[:2] + "****" if k == "smtpPassword" and v else (v or "(未设置)")) for k, v in updates.items()}
    return {"message": "SMTP 配置已更新", "config": masked}
