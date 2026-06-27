"""
成绩查询 + 比对 + 邮件通知
"""
import json
import requests
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from ..models import Student, Grade, NotificationLog, now
from ..schemas import GradeResponse

BASE_URL = "https://jw.ruc.edu.cn"
GRADE_API_PATH = "/resService/jwxtpt/v1/xsd/cjgl_xsxdsq/findKccjList"
RESOURCE_CODE = "XSMH0526"
API_CODE = "jw.xsd.xsdInfo.controller.CjglKccjckController.findKccjList"

TZ = timezone(timedelta(hours=8))

# 全局邮件配置（环境变量优先，可通过 API 动态覆盖）
import os
EMAIL_CONFIG = {
    "smtpHost": os.getenv("SMTP_HOST", "smtp.qq.com"),
    "smtpPort": int(os.getenv("SMTP_PORT", "587")),
    "smtpUsername": os.getenv("SMTP_USERNAME", ""),
    "smtpPassword": os.getenv("SMTP_PASSWORD", ""),
    "fromAddress": os.getenv("SMTP_FROM", ""),
}


def reload_email_config():
    """从数据库加载 SMTP 配置，覆盖环境变量中的空值"""
    try:
        from ..database import SessionLocal
        from ..models import Setting
        db = SessionLocal()
        for k in ["smtpHost", "smtpPort", "smtpUsername", "smtpPassword", "fromAddress"]:
            s = db.query(Setting).filter(Setting.key == k).first()
            if s and s.value:
                EMAIL_CONFIG[k] = int(s.value) if k == "smtpPort" else s.value
        db.close()
    except Exception:
        pass


def update_email_config(config: dict):
    """更新邮件配置（从 config.json 或环境变量加载后调用）"""
    EMAIL_CONFIG.update(config)


def build_headers(res_token: str, session: str, authcode: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "app": "PCWEB",
        "locale": "zh_CN",
        "token": res_token,
        "userrolecode": "student",
        "Cookie": f"SESSION={session}; authcode={authcode}",
        "Referer": "https://jw.ruc.edu.cn/Njw2017/index.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


def fetch_grades_from_api(res_token: str, session: str, authcode: str) -> list[dict] | None:
    """从教务 API 拉取成绩原始数据"""
    url = f"{BASE_URL}{GRADE_API_PATH}?resourceCode={RESOURCE_CODE}&apiCode={API_CODE}"
    headers = build_headers(res_token, session, authcode)

    try:
        resp = requests.post(url, json={}, headers=headers, timeout=15)
    except Exception as e:
        print(f"[grade] 网络异常: {e}")
        return None

    if resp.status_code != 200:
        print(f"[grade] HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()
    if data.get("errorCode") != "success":
        print(f"[grade] API 错误: {data.get('errorMessage', data.get('errorCode'))}")
        return None

    return data.get("data", [])


def sync_grades(db: Session, student: Student, raw_grades: list[dict]) -> dict:
    """将原始成绩数据同步到数据库，返回变动摘要"""
    student_id = student.student_id
    existing = db.query(Grade).filter(Grade.student_id == student_id).all()
    existing_map = {g.cjgl016id: g for g in existing}

    new_grades = []
    updated_grades = []
    current_ids = set()

    for item in raw_grades:
        cjgl016id = item.get("cjgl016id", "")
        course_name = item.get("kcname")
        # 跳过空记录（无 ID 或无课程名）
        if not cjgl016id or not course_name:
            continue
        current_ids.add(cjgl016id)

        cjfscode = str(item.get("cjfscode", "1"))
        # P/F 课程用等级制显示 (P/F)，而非百分制分数 (61)
        if cjfscode == "3":
            score = item.get("zcjname1") or item.get("cjxm3") or "P"
        else:
            score = item.get("zcj") or "-"
        gp = float(item.get("jd", 0) or 0)

        if cjgl016id in existing_map:
            grade_obj = existing_map[cjgl016id]
            old_score = grade_obj.score
            old_gp = grade_obj.grade_point

            if old_score != str(score) or old_gp != gp:
                grade_obj.score = str(score)
                grade_obj.grade_point = gp
                grade_obj.last_updated_at = now()
                updated_grades.append(grade_obj)
        else:
            grade_obj = Grade(
                student_id=student_id,
                cjgl016id=cjgl016id,
                course_code=item.get("kcbh") or "",
                course_name=item.get("kcname") or "",
                score=str(score),
                daily_score=str(item.get("cjxm1") or ""),
                midterm_score=str(item.get("cjxm2") or ""),
                final_score=str(item.get("cjxm3") or ""),
                credit=float(item.get("xf", 0) or 0),
                grade_point=gp,
                semester=item.get("xnxq") or item.get("cjlrxq") or "",
                category=item.get("kclbname") or item.get("kcxzname") or "",
                course_module=item.get("kcmk") or item.get("kcmk_name") or "",
                teacher=item.get("jsname") or "",
                dept=item.get("kkdwname") or "",
                exam_type=item.get("ksxzname") or "",
                grade_note=str(item.get("cjbzname") or ""),
                cjfscode=str(item.get("cjfscode", "1")),
                first_seen_at=now(),
                last_updated_at=now(),
            )
            db.add(grade_obj)
            new_grades.append(grade_obj)

    db.commit()
    return {
        "total": len(raw_grades),
        "new_count": len(new_grades),
        "updated_count": len(updated_grades),
        "new_grades": new_grades,
        "updated_grades": updated_grades,
    }


def send_grade_email(to_address: str, student_name: str, new_grades: list, updated_grades: list):
    """发送成绩变动通知邮件"""
    if not EMAIL_CONFIG.get("smtpUsername"):
        print("[email] 未配置 SMTP，跳过邮件发送")
        return False

    if not to_address:
        print("[email] 未配置收件邮箱")
        return False

    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"{student_name} 的成绩变动通知 — {now_str}", ""]

    if new_grades:
        lines.append(f"新增 {len(new_grades)} 门课程成绩:")
        lines.append("")
        for g in new_grades:
            lines.append(f"  {g.course_name}  {g.score}分  学分{g.credit}  绩点{g.grade_point}  教师:{g.teacher}  {g.semester}")
        lines.append("")

    if updated_grades:
        lines.append(f"更新 {len(updated_grades)} 门课程成绩:")
        lines.append("")
        for g in updated_grades:
            lines.append(f"  {g.course_name}  {g.score}分  学分{g.credit}  绩点{g.grade_point}")
        lines.append("")

    body = "\n".join(lines)

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = EMAIL_CONFIG["fromAddress"]
        msg["To"] = to_address
        parts = []
        if new_grades:
            parts.append(f"新出{len(new_grades)}门")
        if updated_grades:
            parts.append(f"更新{len(updated_grades)}门")
        msg["Subject"] = f"[成绩通知] {'，'.join(parts)}"

        server = smtplib.SMTP(EMAIL_CONFIG["smtpHost"], EMAIL_CONFIG["smtpPort"], timeout=15)
        server.starttls()
        server.login(EMAIL_CONFIG["smtpUsername"], EMAIL_CONFIG["smtpPassword"])
        server.sendmail(EMAIL_CONFIG["fromAddress"], [to_address], msg.as_string())
        server.quit()
        print(f"[email] 已发送至 {to_address}")
        return True
    except Exception as e:
        print(f"[email] 发送失败: {e}")
        return False


def _grade_to_response(g: Grade, is_new: bool = False) -> GradeResponse:
    return GradeResponse(
        id=g.id,
        student_id=g.student_id,
        cjgl016id=g.cjgl016id,
        course_code=g.course_code,
        course_name=g.course_name,
        score=g.score,
        daily_score=g.daily_score or "",
        midterm_score=g.midterm_score or "",
        final_score=g.final_score or "",
        credit=g.credit,
        grade_point=g.grade_point,
        semester=g.semester,
        category=g.category,
        course_module=g.course_module or "",
        teacher=g.teacher,
        dept=g.dept,
        exam_type=g.exam_type,
        grade_note=g.grade_note or "",
        cjfscode=g.cjfscode or "1",
        is_new=is_new,
        first_seen_at=g.first_seen_at,
        last_updated_at=g.last_updated_at,
    )
