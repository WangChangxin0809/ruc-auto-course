"""
登录服务 — 通过学号+密码获取 resToken + SESSION + authcode
"""
import requests
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet
import os

LOGIN_URL = "https://jw.ruc.edu.cn/secService/login"

LOGIN_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "KAPTCHA-KEY-GENERATOR-REDIS": "securityKaptchaRedisServiceAdapter",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

TZ = timezone(timedelta(hours=8))

# 简单密码加密（生产环境应使用环境变量注入的密钥）
_cipher_key_raw = os.getenv("CIPHER_KEY", "")
if not _cipher_key_raw:
    raise RuntimeError("CIPHER_KEY 环境变量未设置！请创建 .env 文件并设置 CIPHER_KEY。参考 .env.example。")
_cipher = Fernet(_cipher_key_raw.encode())


def encrypt_password(password: str) -> str:
    return _cipher.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    return _cipher.decrypt(encrypted.encode()).decode()


USER_INFO_URL = "https://jw.ruc.edu.cn/resService/jwxtpt/v1/jczy/userIndex/findUserDetailNew?resourceCode=XSMH0526&apiCode=jwPublic.controller.UserIndexController.findUserDetailNew"


def fetch_student_info(token: str, session: str, authcode: str) -> dict:
    """获取学生详细信息（姓名、院系、专业、年级）"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "app": "PCWEB",
            "locale": "zh_CN",
            "token": token,
            "userrolecode": "student",
            "Cookie": f"SESSION={session}; authcode={authcode}",
        }
        resp = requests.post(USER_INFO_URL, json={}, headers=headers, timeout=10)
        data = resp.json()
        if data.get("errorCode") == "success":
            xs = data["data"].get("xsInfo", {})
            user = data["data"].get("holder", {}).get("userInfo", {})
            return {
                "name": user.get("username") or xs.get("xs_name") or authcode,
                "major": xs.get("ndzy_name") or "",
                "grade": xs.get("dqszj") or xs.get("rxnf") or "",
                "department": xs.get("skdw_name") or "",
            }
    except Exception as e:
        print(f"[auth] 获取学生信息失败: {e}")
    return {"name": authcode, "major": "", "grade": "", "department": ""}


def do_login(student_id: str, password: str) -> dict | None:
    """登录获取 token + 学生信息，返回 dict 或 None"""
    payload = {
        "userCode": student_id,
        "password": password,
        "kaptcha": "testa",
        "userCodeType": "ldap",
    }

    try:
        resp = requests.post(LOGIN_URL, json=payload, headers=LOGIN_HEADERS, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"[auth] 登录请求异常: {e}")
        return None

    if data.get("errorCode") != "success":
        print(f"[auth] 登录失败: {data.get('errorMessage', '未知错误')}")
        return None

    token = data["data"]["token"]
    session = resp.cookies.get("SESSION", "")
    authcode = data["data"].get("authcode", student_id)

    # 获取学生详细信息
    info = fetch_student_info(token, session, authcode)

    return {
        "resToken": token,
        "session": session,
        "authcode": authcode,
        "name": info["name"],
        "major": info["major"],
        "grade": info["grade"],
        "department": info["department"],
        "token_expires_at": (datetime.now(TZ) + timedelta(hours=3)).replace(tzinfo=None),
    }
