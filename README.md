# UtilityBot

Discord OAuth2でログインし、guildごとにウェルカム／退出カードを編集・プレビューできるFastAPI + discord.py Botです。設定JSONはPydanticで検証し、カードはサーバー側のPillowでPNG化します。Bot tokenが未設定の環境ではWebだけを開発ログインで検証できます。

## ローカル起動

Python 3.12以上を用意し、PowerShellで次を実行します。WindowsではPython 3.13で依存関係のインストールと検証を行っています。

WebとBotをまとめて起動する場合は、プロジェクト直下の`start_utilitybot.bat`をダブルクリックしてください。WebとBotが別々のPowerShellウィンドウで起動し、Web側では先にAlembic migrationを実行します。Webは`http://localhost:8000`で開きます。

```powershell
Copy-Item .env.example .env
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" -m alembic upgrade head
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" run_web.py
```

`http://localhost:8000`を開きます。Discord OAuthでログインすると、管理権限を持つguildを一覧から選び、対象guild名・ID・Bot導入状態を確認してから設定できます。`DEV_AUTH_ENABLED=true`のローカル環境では開発用ログインも利用できますが、画面には「開発モード」と表示され、本番運用の認証には使えません。画面は概要、ウェルカム／退出、モデレーション、サーバー設定のモジュールに分かれています。

Bot workerはWebと別プロセスで起動します。

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" run_bot.py
```

Dockerでは`.env`を作成後、`docker compose up --build`を実行します。PostgreSQLを使う場合は`DATABASE_URL=postgresql+asyncpg://utilitybot:change-me-in-local-env@db:5432/utilitybot`に変更し、コンテナ内で`alembic upgrade head`を実行してください。

## 環境変数

`BOT_TOKEN`、`DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`DATABASE_URL`、`SESSION_SECRET`、`DISCORD_REDIRECT_URI`、`ALLOWED_ORIGINS`、`COOKIE_SECURE`が主要設定です。Minecraft連携を使う場合は`MC_SERVER_ADDRESS`（例: `play.example.net:25565`）と`MC_SERVER_TIMEOUT_SECONDS`も設定します。secretは`.env`またはsecret managerで渡し、Gitに追加しません。`SESSION_SECRET`は本番で32文字以上のランダム値に変更し、HTTPSでは`COOKIE_SECURE=true`にします。

Discord OAuthは`identify guilds` scopeのauthorization codeフローを使用します。Developer Portalのredirect URIを`DISCORD_REDIRECT_URI`と完全一致させてください。callbackではstateをCookieとサーバー側の一時状態で照合し、一度検証したstateを破棄したうえでtoken交換とユーザー／guild情報取得を行い、ユーザープロフィールをDBへ保存します。OAuthの実ブラウザログインはDiscordの資格情報が必要なため、ローカルの自動テスト対象外です。資格情報がない場合は日本語の設定不足エラーを返し、開発ログインで外部APIなしの検証ができます。なお、現在のguild認可キャッシュは単一プロセスのメモリ上に保持するため、本番の複数Web workerでは共有セッション／Redis等へ移行してください。

## Discord設定・権限

BotにはView Channels、Send Messages、Attach Files、Embed Linksを基本権限として与え、モデレーションを使うguildだけModerate Members、Kick Members、Ban Membersを追加します。管理者権限の一括要求はしません。`GUILD_MEMBERS` privileged intentをDeveloper Portalで有効化してください。MESSAGE_CONTENTとPresenceは要求しません。

Slash commandは`/ping`、`/server status`、`/manage status/show/welcome_test/leave_test/set_channel`、`/mod warn/timeout/untimeout/kick/ban/unban/warnings/clear_warnings`です。`manage`配下の設定表示・送信先変更・テスト送信で、Web管理画面の主要な日常操作もDiscordから実行できます。全説明は日本語で、操作前に実行者の権限・対象のロール階層を検査します。Bot tokenを複数workerで起動しないでください。

## APIとセキュリティ

`/health/live`、`/health/ready`、guild設定、welcome/leave CRUD、PNG preview、warnings一覧を提供します。guild IDは毎回認可し、開発モードでも`DEV_GUILD_ID`以外は403です。変更系は`X-CSRF-Token`を要求し、秘密情報はレスポンス・ログ・カードに保存しません。JSON要素は許可リスト、座標0〜1、サイズ・文字数上限を適用します。

本番ではHTTPS、CSP、共有DB/Redisセッション、DBバックアップ、ログrotate、リバースプロキシのtrusted設定を有効化してください。OAuth実連携、Botのjoin/leave実送信、Discord権限不足時の表示、Developer Portal設定は外部資格情報が必要な手動確認です。

## 検証

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check src tests
```
