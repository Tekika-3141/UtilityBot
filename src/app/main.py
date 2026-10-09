from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import secrets
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import get_user_id, set_session, verify_csrf
from .cards import CardDocument, render_card
from .config import get_settings
from .db import Guild, GuildSetting, SessionLocal, User, Warning, WelcomeConfig, get_session, init_db

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="UtilityBot Dashboard", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])
oauth_states: set[str] = set()
oauth_guilds: dict[str, list[dict]] = {}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin", "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"})
    if request.method in {"POST", "PUT", "DELETE"} and request.url.path.startswith("/api/"):
        token = request.headers.get("X-CSRF-Token")
        if not token and request.url.path != "/api/v1/dev-login":
            response.status_code = 403
    return response


class WelcomeInput(BaseModel):
    enabled: bool = False
    channel_id: str | None = Field(default=None, max_length=32)
    message_template: str = Field(default="{mention} さん、ようこそ！", max_length=1000)
    card_document: CardDocument = Field(default_factory=CardDocument)


class SettingsInput(BaseModel):
    locale: str = Field(default="ja", pattern="^[a-z]{2}$")
    timezone: str = Field(default="Asia/Tokyo", max_length=50)
    welcome_channel_id: str | None = Field(default=None, max_length=32)
    leave_channel_id: str | None = Field(default=None, max_length=32)
    mod_log_channel_id: str | None = Field(default=None, max_length=32)


async def authorized_guild(guild_id: str, request: Request, db: AsyncSession) -> Guild:
    user_id = get_user_id(request)
    if get_settings().dev_auth_enabled and guild_id != get_settings().dev_guild_id:
        raise HTTPException(403, "このサーバーを管理する権限を確認できません")
    if not get_settings().dev_auth_enabled and not any(guild["id"] == guild_id for guild in oauth_guilds.get(user_id, [])):
        raise HTTPException(403, "このサーバーを管理する権限を確認できません")
    guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == guild_id))
    if not guild:
        guild = Guild(discord_guild_id=guild_id, name="開発サーバー" if get_settings().dev_auth_enabled else "Discord Guild", bot_present=True)
        db.add(guild)
        await db.flush()
    return guild


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_session)):
    await db.execute(select(func.count()).select_from(Guild))
    return {"status": "ready"}


@app.post("/api/v1/dev-login")
async def dev_login(response: Response):
    if not get_settings().dev_auth_enabled:
        raise HTTPException(404, "開発ログインは無効です")
    response.set_cookie("utilitybot_dev", "1", httponly=True, samesite="lax")
    response.set_cookie("utilitybot_csrf", "dev-csrf-token", httponly=False, samesite="lax")
    return {"message": "開発用ログインしました"}


@app.get("/auth/discord/login")
async def discord_login():
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_client_secret:
        raise HTTPException(503, "Discord OAuthの設定がありません。.envにclient IDとsecretを設定してください")
    state = secrets.token_urlsafe(32)
    oauth_states.add(state)
    response = RedirectResponse(f"https://discord.com/oauth2/authorize?client_id={settings.discord_client_id}&response_type=code&redirect_uri={settings.discord_redirect_uri}&scope=identify%20guilds&state={state}")
    response.set_cookie("oauth_state", state, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=600)
    return response


@app.get("/auth/discord/callback")
async def discord_callback(code: str, state: str, request: Request):
    settings = get_settings()
    expected = request.cookies.get("oauth_state")
    if not expected or not secrets.compare_digest(expected, state) or state not in oauth_states:
        raise HTTPException(400, "OAuth stateが無効です。もう一度ログインしてください")
    oauth_states.discard(state)
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post("https://discord.com/api/v10/oauth2/token", data={
            "client_id": settings.discord_client_id, "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code", "code": code, "redirect_uri": settings.discord_redirect_uri,
        })
        if token_response.is_error:
            raise HTTPException(502, "Discord OAuthの認証に失敗しました")
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_response = await client.get("https://discord.com/api/v10/users/@me", headers=headers)
        guild_response = await client.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
    if user_response.is_error or guild_response.is_error:
        raise HTTPException(502, "Discord情報を取得できませんでした")
    user = user_response.json()
    user_id = str(user["id"])
    oauth_guilds[user_id] = [guild for guild in guild_response.json() if int(guild.get("permissions", 0)) & (1 << 5) or guild.get("owner")]
    async with SessionLocal() as db:
        stored_user = await db.scalar(select(User).where(User.discord_user_id == user_id))
        if not stored_user:
            stored_user = User(discord_user_id=user_id, username=user.get("username", "Discordユーザー"),
                               display_name=user.get("global_name") or user.get("username", "Discordユーザー"),
                               avatar=user.get("avatar"))
            db.add(stored_user)
        else:
            stored_user.username = user.get("username", stored_user.username)
            stored_user.display_name = user.get("global_name") or user.get("username", stored_user.display_name)
            stored_user.avatar = user.get("avatar")
        await db.commit()
    redirect = RedirectResponse("/")
    set_session(redirect, user_id)
    redirect.set_cookie("utilitybot_csrf", secrets.token_urlsafe(32), httponly=False, secure=settings.cookie_secure, samesite="lax")
    return redirect


@app.get("/api/v1/me")
async def me(request: Request, db: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    user = await db.scalar(select(User).where(User.discord_user_id == user_id))
    return {"discord_user_id": user_id, "display_name": user.display_name if user else "開発ユーザー"}


@app.get("/api/v1/session")
async def session_info(request: Request, db: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    is_dev = get_settings().dev_auth_enabled and request.cookies.get("utilitybot_dev") == "1"
    user = await db.scalar(select(User).where(User.discord_user_id == user_id))
    return {
        "authenticated": True,
        "mode": "development" if is_dev else "discord",
        "discord_user_id": user_id,
        "display_name": user.display_name if user else ("開発ユーザー" if is_dev else "Discordユーザー"),
    }


@app.get("/api/v1/guilds")
async def guilds(request: Request, db: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    if get_settings().dev_auth_enabled:
        guild = await authorized_guild(get_settings().dev_guild_id, request, db)
        await db.commit()
        return [{"id": guild.discord_guild_id, "name": guild.name, "bot_present": guild.bot_present, "manageable": True}]
    result = []
    for guild in oauth_guilds.get(user_id, []):
        stored = await db.scalar(select(Guild).where(Guild.discord_guild_id == guild["id"]))
        result.append({
            "id": guild["id"],
            "name": guild["name"],
            "bot_present": bool(stored and stored.bot_present),
            "manageable": True,
        })
    return result


@app.get("/api/v1/guilds/{guild_id}")
async def guild_detail(guild_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    guild = await authorized_guild(guild_id, request, db)
    return {"id": guild.discord_guild_id, "name": guild.name, "bot_present": guild.bot_present}


@app.get("/api/v1/guilds/{guild_id}/settings")
async def get_settings_api(guild_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    guild = await authorized_guild(guild_id, request, db)
    settings = await db.scalar(select(GuildSetting).where(GuildSetting.guild_id == guild.id))
    if not settings:
        settings = GuildSetting(guild_id=guild.id)
        db.add(settings)
        await db.commit()
    return {key: getattr(settings, key) for key in ("locale", "timezone", "welcome_channel_id", "leave_channel_id", "mod_log_channel_id")}


@app.put("/api/v1/guilds/{guild_id}/settings")
async def update_settings(guild_id: str, payload: SettingsInput, request: Request, x_csrf_token: str | None = Header(default=None), db: AsyncSession = Depends(get_session)):
    verify_csrf(request, x_csrf_token)
    guild = await authorized_guild(guild_id, request, db)
    settings = await db.scalar(select(GuildSetting).where(GuildSetting.guild_id == guild.id))
    if not settings:
        settings = GuildSetting(guild_id=guild.id)
        db.add(settings)
    for key, value in payload.model_dump().items():
        setattr(settings, key, value)
    settings.updated_by = get_user_id(request)
    await db.commit()
    return payload.model_dump()


@app.get("/api/v1/guilds/{guild_id}/welcome/{event_type}")
async def get_welcome(guild_id: str, event_type: str, request: Request, db: AsyncSession = Depends(get_session)):
    if event_type not in {"join", "leave"}:
        raise HTTPException(422, "event_typeはjoinまたはleaveです")
    guild = await authorized_guild(guild_id, request, db)
    config = await db.scalar(select(WelcomeConfig).where(WelcomeConfig.guild_id == guild.id, WelcomeConfig.event_type == event_type))
    if not config:
        config = WelcomeConfig(guild_id=guild.id, event_type=event_type, card_document=CardDocument().model_dump())
        db.add(config)
        await db.commit()
    return {"enabled": config.enabled, "channel_id": config.channel_id, "message_template": config.message_template, "card_document": config.card_document}


@app.put("/api/v1/guilds/{guild_id}/welcome/{event_type}")
async def update_welcome(guild_id: str, event_type: str, payload: WelcomeInput, request: Request, x_csrf_token: str | None = Header(default=None), db: AsyncSession = Depends(get_session)):
    verify_csrf(request, x_csrf_token)
    if event_type not in {"join", "leave"}:
        raise HTTPException(422, "event_typeはjoinまたはleaveです")
    guild = await authorized_guild(guild_id, request, db)
    config = await db.scalar(select(WelcomeConfig).where(WelcomeConfig.guild_id == guild.id, WelcomeConfig.event_type == event_type))
    if not config:
        config = WelcomeConfig(guild_id=guild.id, event_type=event_type)
        db.add(config)
    config.enabled, config.channel_id, config.message_template = payload.enabled, payload.channel_id, payload.message_template
    config.card_document, config.updated_by = payload.card_document.model_dump(), get_user_id(request)
    await db.commit()
    return payload.model_dump()


@app.post("/api/v1/guilds/{guild_id}/welcome/{event_type}/preview")
async def preview(guild_id: str, event_type: str, payload: CardDocument, request: Request, db: AsyncSession = Depends(get_session)):
    await authorized_guild(guild_id, request, db)
    return Response(render_card(payload, {"username": "サンプルユーザー", "guild_name": "サンプルサーバー"}), media_type="image/png")


@app.get("/api/v1/guilds/{guild_id}/warnings")
async def warnings(guild_id: str, request: Request, page: int = 1, db: AsyncSession = Depends(get_session)):
    guild = await authorized_guild(guild_id, request, db)
    page = max(page, 1)
    rows = (await db.scalars(select(Warning).where(Warning.guild_id == guild.id, Warning.deleted_at.is_(None)).order_by(Warning.id.desc()).offset((page - 1) * 20).limit(20))).all()
    return {"page": page, "items": [{"id": row.id, "target_discord_user_id": row.target_discord_user_id, "reason": row.reason, "created_at": row.created_at.isoformat()} for row in rows]}


@app.post("/api/v1/logout")
async def logout(response: Response):
    response.delete_cookie("utilitybot_session")
    response.delete_cookie("utilitybot_dev")
    return {"message": "ログアウトしました"}
