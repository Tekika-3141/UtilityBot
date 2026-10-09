import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from .config import get_settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="utilitybot-session")


def set_session(response: Response, user_id: str) -> None:
    value = _serializer().dumps({"user_id": user_id, "expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    response.set_cookie("utilitybot_session", value, httponly=True, secure=get_settings().cookie_secure, samesite="lax", max_age=3600)


def get_user_id(request: Request) -> str:
    if get_settings().dev_auth_enabled and request.cookies.get("utilitybot_dev") == "1":
        return get_settings().dev_discord_user_id
    value = request.cookies.get("utilitybot_session")
    if not value:
        if get_settings().dev_auth_enabled:
            return get_settings().dev_discord_user_id
        raise HTTPException(401, "ログインが必要です")
    try:
        data = _serializer().loads(value, max_age=get_settings().session_ttl_seconds)
        return str(data["user_id"])
    except (BadSignature, KeyError) as exc:
        raise HTTPException(401, "セッションが無効または期限切れです") from exc


def csrf_token(request: Request) -> str:
    token = request.cookies.get("utilitybot_csrf")
    if token:
        return token
    token = secrets.token_urlsafe(32)
    request.state.csrf_token = token
    return token


def verify_csrf(request: Request, token: str | None) -> None:
    expected = request.cookies.get("utilitybot_csrf")
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(403, "CSRFトークンが無効です")


def session_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
