from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("discord_user_id", sa.String(32), unique=True, nullable=False), sa.Column("username", sa.String(100), nullable=False), sa.Column("display_name", sa.String(100), nullable=False), sa.Column("avatar", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("guilds", sa.Column("id", sa.Integer, primary_key=True), sa.Column("discord_guild_id", sa.String(32), unique=True, nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("bot_present", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("guild_settings", sa.Column("id", sa.Integer, primary_key=True), sa.Column("guild_id", sa.Integer, sa.ForeignKey("guilds.id"), unique=True), sa.Column("locale", sa.String(10), nullable=False), sa.Column("timezone", sa.String(50), nullable=False), sa.Column("welcome_channel_id", sa.String(32)), sa.Column("leave_channel_id", sa.String(32)), sa.Column("mod_log_channel_id", sa.String(32)), sa.Column("updated_by", sa.String(32)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("welcome_configs", sa.Column("id", sa.Integer, primary_key=True), sa.Column("guild_id", sa.Integer, sa.ForeignKey("guilds.id")), sa.Column("event_type", sa.String(10)), sa.Column("enabled", sa.Boolean, nullable=False), sa.Column("channel_id", sa.String(32)), sa.Column("message_template", sa.Text, nullable=False), sa.Column("card_document", sa.JSON, nullable=False), sa.Column("schema_version", sa.Integer, nullable=False), sa.Column("updated_by", sa.String(32)), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("guild_id", "event_type"))
    op.create_table("warnings", sa.Column("id", sa.Integer, primary_key=True), sa.Column("guild_id", sa.Integer, sa.ForeignKey("guilds.id")), sa.Column("target_discord_user_id", sa.String(32)), sa.Column("moderator_discord_user_id", sa.String(32)), sa.Column("reason", sa.String(1000)), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("deleted_at", sa.DateTime(timezone=True)))

def downgrade():
    for table in ("warnings", "welcome_configs", "guild_settings", "guilds", "users"):
        op.drop_table(table)
