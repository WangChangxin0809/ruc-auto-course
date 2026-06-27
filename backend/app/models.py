import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base

TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ).replace(tzinfo=None)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(50), default="")
    password = Column(Text, nullable=False)
    email = Column(String(100), default="")
    major = Column(String(100), default="")
    grade = Column(String(20), default="")
    res_token = Column(Text, default="")
    session = Column(String(100), default="")
    authcode = Column(String(20), default="")
    token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_monitored = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    cjgl016id = Column(String(50), nullable=False, unique=True)
    course_code = Column(String(50), default="")
    course_name = Column(String(200), default="")
    score = Column(String(20), default="")
    daily_score = Column(String(20), default="")
    midterm_score = Column(String(20), default="")
    final_score = Column(String(20), default="")
    credit = Column(Float, default=0)
    grade_point = Column(Float, default=0)
    semester = Column(String(50), default="")
    category = Column(String(100), default="")
    course_module = Column(String(100), default="")
    teacher = Column(String(50), default="")
    dept = Column(String(100), default="")
    exam_type = Column(String(50), default="")
    grade_note = Column(String(50), default="")
    cjfscode = Column(String(5), default="1")
    first_seen_at = Column(DateTime, default=now)
    last_updated_at = Column(DateTime, default=now, onupdate=now)

    student = relationship("Student", back_populates="grades")


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), nullable=False, index=True)
    grade_ids = Column(Text, default="[]")
    change_type = Column(String(20), default="new")
    sent_at = Column(DateTime, default=now)

    def get_grade_ids(self):
        return json.loads(self.grade_ids) if self.grade_ids else []


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(50), primary_key=True)
    value = Column(Text, default="")
