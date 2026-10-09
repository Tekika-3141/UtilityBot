import io
import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from mcstatus import JavaServer
from sqlalchemy import select

from .cards import CardDocument, render_card
from .config import get_settings
from .db import Guild, SessionLocal, Warning, WelcomeConfig

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def replace_variables(template: str, member: discord.Member | discord.User, guild: discord.Guild) -> str:
    return (
        template.replace("{mention}", member.mention)
        .replace("{username}", member.name)
        .replace("{guild_name}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
    )


class UtilityBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(ManagementCog(self))
        await self.add_cog(ModerationCog(self))
        await self.add_cog(MinecraftCog(self))
        await self.add_cog(UtilityCog(self))
        await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("Bot接続成功: guilds=%d", len(self.guilds))

    async def on_member_join(self, member: discord.Member) -> None:
        await self._send_event(member, "join")

    async def on_member_remove(self, member: discord.Member) -> None:
        await self._send_event(member, "leave")

    async def _send_event(self, member: discord.Member, event_type: str, channel: discord.TextChannel | None = None) -> None:
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(member.guild.id)))
            if not guild:
                return
            config = await db.scalar(
                select(WelcomeConfig).where(
                    WelcomeConfig.guild_id == guild.id, WelcomeConfig.event_type == event_type
                )
            )
            if not config or not config.enabled or not config.channel_id:
                return
            target = channel or self.get_channel(int(config.channel_id))
            if not isinstance(target, discord.TextChannel):
                return
            content = replace_variables(config.message_template, member, member.guild)
            avatar = None
            try:
                avatar = await member.display_avatar.with_size(256).read()
            except (discord.HTTPException, discord.NotFound):
                log.warning("アバター取得に失敗しました: guild=%s user=%s", member.guild.id, member.id)
            image = render_card(
                CardDocument.model_validate(config.card_document),
                {
                    "username": member.name,
                    "guild_name": member.guild.name,
                    "avatar": avatar,
                },
            )
            await target.send(
                content=content[:2000],
                file=discord.File(fp=io.BytesIO(image), filename="welcome-card.png"),
                allowed_mentions=discord.AllowedMentions(users=True),
            )


class ManagementCog(commands.Cog):
    manage = app_commands.Group(name="manage", description="サーバーの設定確認やテスト送信を行います")

    def __init__(self, bot: UtilityBot) -> None:
        self.bot = bot

    @manage.command(name="status", description="Bot権限とウェルカム機能の状態を表示します")
    async def status(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return
        me = interaction.guild.me
        permissions = me.guild_permissions if me else None
        await interaction.response.send_message(
            f"接続済みです。メンバー数: {interaction.guild.member_count or 0}、"
            f"メッセージ送信: {'可' if permissions and permissions.send_messages else '不可'}",
            ephemeral=True,
        )

    @manage.command(name="show", description="現在のウェルカムと退出設定を表示します")
    async def show(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(interaction.guild.id)))
            if not guild:
                await interaction.response.send_message("先にWeb管理画面でサーバーを初期化してください。", ephemeral=True)
                return
            configs = (
                await db.scalars(select(WelcomeConfig).where(WelcomeConfig.guild_id == guild.id))
            ).all()
        summary = " / ".join(
            f"{'参加' if config.event_type == 'join' else '退出'}: "
            f"{'有効' if config.enabled else '無効'}・<#${config.channel_id}>".replace("<#$", "<#")
            for config in configs
        ) or "設定なし"
        await interaction.response.send_message(summary, ephemeral=True)

    async def _test_event(self, interaction: discord.Interaction, event_type: str, member: discord.Member | None) -> None:
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("サーバーのテキストチャンネルで実行してください。", ephemeral=True)
            return
        target = member or interaction.user
        if not isinstance(target, (discord.Member, discord.User)):
            await interaction.response.send_message("対象ユーザーを取得できません。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await self.bot._send_event(target, event_type, interaction.channel)
        await interaction.followup.send("テスト送信しました。", ephemeral=True)

    @manage.command(name="welcome_test", description="参加メッセージを現在のチャンネルへテスト送信します")
    @app_commands.describe(user="画像に使用するメンバー（省略時は自分）")
    async def welcome_test(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await self._test_event(interaction, "join", user)

    @manage.command(name="leave_test", description="退出メッセージを現在のチャンネルへテスト送信します")
    @app_commands.describe(user="画像に使用するメンバー（省略時は自分）")
    async def leave_test(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await self._test_event(interaction, "leave", user)

    @manage.command(name="set_channel", description="参加または退出メッセージの送信先を設定します")
    @app_commands.describe(event="joinまたはleave", channel="送信先チャンネル")
    @app_commands.choices(event=[
        app_commands.Choice(name="参加", value="join"),
        app_commands.Choice(name="退出", value="leave"),
    ])
    async def set_channel(self, interaction: discord.Interaction, event: app_commands.Choice[str], channel: discord.TextChannel) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("サーバー管理権限が必要です。", ephemeral=True)
            return
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(interaction.guild.id)))
            if not guild:
                await interaction.response.send_message("先にWeb管理画面でサーバーを初期化してください。", ephemeral=True)
                return
            config = await db.scalar(select(WelcomeConfig).where(
                WelcomeConfig.guild_id == guild.id, WelcomeConfig.event_type == event.value
            ))
            if not config:
                config = WelcomeConfig(guild_id=guild.id, event_type=event.value, card_document=CardDocument().model_dump())
                db.add(config)
            config.channel_id = str(channel.id)
            await db.commit()
        await interaction.response.send_message(f"{event.name}メッセージの送信先を {channel.mention} に設定しました。", ephemeral=True)

    @manage.command(name="help", description="利用できる管理コマンドを表示します")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "manage status/show/welcome_test/leave_test/set_channel、"
            "mod warn/timeout/untimeout/kick/ban/unban/warnings/clear_warnings、"
            "ping、server status が利用できます。",
            ephemeral=True,
        )


class MinecraftCog(commands.Cog):
    server = app_commands.Group(name="server", description="Minecraftサーバーの情報を確認します")

    def __init__(self, bot: UtilityBot) -> None:
        self.bot = bot

    @server.command(name="status", description="設定したMinecraftサーバーの稼働状況を確認します")
    async def status(self, interaction: discord.Interaction) -> None:
        address = get_settings().mc_server_address
        if not address:
            await interaction.response.send_message("MC_SERVER_ADDRESSが未設定です。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            server = await JavaServer.async_lookup(address, timeout=get_settings().mc_server_timeout_seconds)
            status = await server.async_status()
            await interaction.followup.send(
                f"🟢 Minecraftサーバーはオンラインです\n"
                f"アドレス: `{address}`\nプレイヤー: {status.players.online}/{status.players.max}\n"
                f"レイテンシ: {status.latency:.0f}ms",
                ephemeral=True,
            )
        except Exception:
            await interaction.followup.send(f"🔴 `{address}` に接続できませんでした。", ephemeral=True)


class UtilityCog(commands.Cog):
    def __init__(self, bot: UtilityBot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Botの応答速度を確認します")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"Pong! {self.bot.latency * 1000:.0f}ms", ephemeral=False)


class ModerationCog(commands.Cog):
    mod = app_commands.Group(name="mod", description="メンバーへの警告や管理操作を行います")

    def __init__(self, bot: UtilityBot) -> None:
        self.bot = bot

    async def _check(self, interaction: discord.Interaction, member: discord.Member) -> bool:
        actor = interaction.user
        if not interaction.guild or not isinstance(actor, discord.Member) or not actor.guild_permissions.moderate_members:
            await interaction.response.send_message("モデレーション権限が必要です。", ephemeral=True)
            return False
        if member == actor or member == interaction.guild.me or member.top_role >= actor.top_role:
            await interaction.response.send_message("対象のロール階層を操作できません。", ephemeral=True)
            return False
        return True

    @mod.command(name="warn", description="メンバーに警告を記録します")
    @app_commands.describe(user="警告対象のメンバー", reason="警告理由")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし") -> None:
        if not await self._check(interaction, user):
            return
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(interaction.guild.id)))
            if not guild:
                await interaction.response.send_message("このサーバーはWeb管理画面で初期化されていません。", ephemeral=True)
                return
            db.add(Warning(guild_id=guild.id, target_discord_user_id=str(user.id),
                           moderator_discord_user_id=str(interaction.user.id), reason=reason[:1000]))
            await db.commit()
        await interaction.response.send_message(f"{user.mention} に警告を記録しました。", ephemeral=True)

    @mod.command(name="timeout", description="メンバーを指定分数タイムアウトします")
    @app_commands.describe(user="対象メンバー", duration_minutes="1〜40320分", reason="理由")
    async def timeout(self, interaction: discord.Interaction, user: discord.Member,
                      duration_minutes: app_commands.Range[int, 1, 40320], reason: str = "理由なし") -> None:
        if not await self._check(interaction, user):
            return
        try:
            await user.timeout(timedelta(minutes=duration_minutes), reason=reason[:512])
            await interaction.response.send_message("タイムアウトしました。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Discord APIが操作を拒否しました。", ephemeral=True)

    @mod.command(name="untimeout", description="メンバーのタイムアウトを解除します")
    @app_commands.describe(user="対象メンバー", reason="理由")
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし") -> None:
        if await self._check(interaction, user):
            try:
                await user.timeout(None, reason=reason[:512])
                await interaction.response.send_message("タイムアウトを解除しました。", ephemeral=True)
            except discord.HTTPException:
                await interaction.response.send_message("Discord APIが操作を拒否しました。", ephemeral=True)

    @mod.command(name="kick", description="メンバーをサーバーからキックします")
    @app_commands.describe(user="対象メンバー", reason="理由")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし") -> None:
        if await self._check(interaction, user):
            try:
                await user.kick(reason=reason[:512])
                await interaction.response.send_message("キックしました。", ephemeral=True)
            except discord.HTTPException:
                await interaction.response.send_message("Discord APIが操作を拒否しました。", ephemeral=True)

    @mod.command(name="ban", description="メンバーをサーバーからBANします")
    @app_commands.describe(user="対象メンバー", reason="理由", delete_message_days="削除する過去メッセージ日数(0〜7)")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし",
                  delete_message_days: app_commands.Range[int, 0, 7] = 0) -> None:
        if await self._check(interaction, user):
            try:
                await user.ban(reason=reason[:512], delete_message_seconds=delete_message_days * 86400)
                await interaction.response.send_message("BANしました。", ephemeral=True)
            except discord.HTTPException:
                await interaction.response.send_message("Discord APIが操作を拒否しました。", ephemeral=True)

    @mod.command(name="unban", description="ユーザーIDのBANを解除します")
    @app_commands.describe(user_id="BAN解除するDiscordユーザーID", reason="理由")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "理由なし") -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("BAN権限が必要です。", ephemeral=True)
            return
        try:
            await interaction.guild.unban(discord.Object(id=int(user_id)), reason=reason[:512])
            await interaction.response.send_message("BANを解除しました。", ephemeral=True)
        except (ValueError, discord.HTTPException):
            await interaction.response.send_message("ユーザーIDが不正か、BAN解除に失敗しました。", ephemeral=True)

    @mod.command(name="warnings", description="メンバーの警告一覧を表示します")
    @app_commands.describe(user="対象メンバー", page="ページ番号")
    async def warnings(self, interaction: discord.Interaction, user: discord.Member, page: app_commands.Range[int, 1, 100] = 1) -> None:
        if not await self._check(interaction, user):
            return
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(interaction.guild.id)))
            rows = [] if not guild else (await db.scalars(select(Warning).where(
                Warning.guild_id == guild.id, Warning.target_discord_user_id == str(user.id),
                Warning.deleted_at.is_(None)).order_by(Warning.id.desc()).offset((page - 1) * 10).limit(10))).all()
        message = "\n".join(f"#{row.id}: {row.reason}" for row in rows) or "警告はありません。"
        await interaction.response.send_message(message[:1900], ephemeral=True)

    @mod.command(name="clear_warnings", description="メンバーの警告をすべて削除します")
    @app_commands.describe(user="対象メンバー")
    async def clear_warnings(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._check(interaction, user):
            return
        async with SessionLocal() as db:
            guild = await db.scalar(select(Guild).where(Guild.discord_guild_id == str(interaction.guild.id)))
            if guild:
                rows = (await db.scalars(select(Warning).where(
                    Warning.guild_id == guild.id, Warning.target_discord_user_id == str(user.id),
                    Warning.deleted_at.is_(None)))).all()
                for row in rows:
                    row.deleted_at = discord.utils.utcnow()
                await db.commit()
        await interaction.response.send_message(f"{user.mention} の警告を削除しました。", ephemeral=True)


async def run_bot() -> None:
    token = get_settings().bot_token
    if not token:
        log.error("BOT_TOKENが未設定です。.envに設定してBot workerを起動してください")
        return
    await UtilityBot().start(token)
