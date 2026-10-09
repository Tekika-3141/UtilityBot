# GitHub Copilot Chat（VS Code）への実装依頼書：Web管理型DiscordコミュニティBot

あなたはVS Code上のGitHub Copilot Chatで作業するシニアPythonエンジニア兼プロダクトエンジニアです。現在開いているワークスペースのファイルを調査・編集し、ターミナルやテスト実行機能が利用可能なら活用して、以下の要件を満たす本番運用を意識したPython Discord BotとWebダッシュボードを実装してください。作業対象は現在開いているワークスペースだけです。

## 0. 最優先の進め方

- 最初にワークスペース内のファイル、README、既存コード、設定、Git差分を確認し、既存資産とユーザーの未コミット変更を尊重してください。既存ファイルを一括上書きせず、必要な範囲だけ編集します。
- 最初に短い実装計画と前提を提示してから、計画だけで止まらず実装してください。重大な不明点がなければ妥当な既定値で進めます。
- VS Codeの編集機能でファイルを直接作成・更新してください。コードをチャットに貼るだけで完了扱いにしてはいけません。必須ファイルをTODOやplaceholderで省略しないでください。
- 大きな変更は基盤、認証、カード編集、Bot機能、テスト・運用のように小さなまとまりで進め、各段階で変更内容と次の作業を短く示してください。コンテキストや応答量の制限がある場合は、完了済み・未完了・次に触るファイルを記録し、ユーザーが「続けて」と言ったらそこから再開してください。
- ターミナルやテスト実行機能が使える場合は、依存インストール、migration、lint、型検査、テスト、ビルドを実行してください。使えない機能や外部資格情報がない場合はその項目だけを未実行とし、実行したように報告しないでください。
- 各フェーズ終了時に、変更ファイル、実行した検証と結果、未実行の確認と理由、次の作業を短く報告してください。最終的に全機能を統合した動作可能なアプリを完成させます。
- 外部サービスの資格情報がない場合でも、`.env.example`、開発用モード、明確なセットアップ手順を用意し、資格情報を設定した後に動作する実装を完了してください。実際のDiscord接続を偽装して成功扱いにしないでください。
- 仕様の追従性が必要なDiscord API、discord.py、フレームワーク、依存ライブラリの仕様は実装時点の公式資料を確認してください。互換性を確認して依存バージョンを固定し、`pyproject.toml` と lock file に反映してください。
- UI文言、README、利用者向けエラーは日本語を基本にしてください。コード識別子・内部ログは英語で構いません。
- ProBot/Dynoのブランド、コード、画像、文言を複製せず、一般的な機能カテゴリを参考に独自実装してください。

## 1. 目的と運用範囲

自分のコミュニティで最初に運用し、後から他のDiscordサーバー（以下 guild）にも招待して提供できる、Python製の多guild対応BotとWeb管理サイトを作ります。利用者はDiscord OAuth2でログインし、自分が管理権限を持ち、かつBotが参加しているguildごとに設定します。公式コミュニティドメインを使う想定ですが、ドメイン名はハードコードしません。

中心価値は、ウェルカム／退出メッセージを画像カードとして自由にデザインできること、運営設定をWebで完結できること、基本的なモデレーションとログ機能を一元化することです。

## 2. 技術要件とDiscord仕様

- Python 3.12以上を推奨し、利用するホスティング環境で対応する安定版を固定してください。
- Discord Gatewayとslash commandは `discord.py` 2.x（実装時点で利用可能な最新安定版。現在の基準は2.7.1、Python 3.8+）を使用し、async/awaitを一貫させます。ユーザーアカウントの自動化（self-bot）やユーザートークン利用は禁止です。
- WebはFastAPI（async対応）、ORMはSQLAlchemy 2.x async、migrationはAlembic、DBはPostgreSQLを標準とします。ローカル開発用にSQLiteを許容しても、PostgreSQLとの機能差を明記し、SQLite固有機能に依存しないこと。
- UIはサーバー描画またはReact/Vue等から、リポジトリ規模に合う一つを選択し、ドラッグ編集・プレビューが快適に動く実装を含めます。フロントエンドを採る場合は型検査・ビルド手順を整備します。
- Discord API v10を前提に、Interactionは3秒以内に初期応答し、必要ならdefer後にfollow-upを返します。429/レート制限、権限不足、Bot未導入、対象チャンネル消失を適切に処理します。
- Slash command名・オプション名はDiscord制約に従い、説明は各1〜100文字、コマンドオプションは最大25個です。必須オプションを先に定義します。表示名・説明には日本語ローカライズを設定し、Discordで許容される名前形式を守ります。
- 参加/退出イベントには `GUILD_MEMBERS` privileged intent が必要です。Developer Portalでの有効化、規模によるDiscord承認要否、導入時の設定手順をREADMEに明記します。必要なIntentだけを有効にします。初期リリースでは全メッセージ本文を監視する機能を入れず、`MESSAGE_CONTENT` intentを要求しません。
- 必要Intentは原則 `guilds`, `guild_members`, `guild_moderation`（実装機能に必要な場合）, `guild_messages`（必要なイベントだけ）とし、Presenceは要求しません。設計上必要な機能とIntentの対応表をREADMEに記載します。
- OAuth2は `identify` と `guilds` scopeを使い、サーバー側でauthorization codeを交換します。ユーザーがBotの参加guild一覧から選ぶ方式です。OAuth一覧だけを認可の根拠にせず、guild内権限（ownerまたはManage Guild/Administrator）をサーバー側で都度検証します。`guilds.join`やユーザーを勝手にguildへ追加するフローは使いません。

## 3. 初回リリースの機能範囲

### 必須：認証・guild管理

- Discord OAuth2ログイン、ログアウト、CSRF対策、セッション有効期限、guild選択。
- ログイン利用者が管理できるguildのみ一覧表示。必要ならDiscord APIから取得した情報を短時間キャッシュし、Bot接続状態・権限不足・未導入を表示します。
- guild単位の設定取得・更新、設定変更履歴、保存成功/失敗表示。
- Bot招待リンクを提供し、必要最低限の権限だけを要求。管理者権限を一括要求しない。

### 必須：ウェルカム／退出カード

- join/leaveそれぞれ有効化、送信先チャンネル選択、テキスト本文、画像カード、メンション方針、テストプレビュー、実際のテスト送信。
- ブラウザ上のキャンバスで背景画像（アップロードまたは安全なURL指定）、背景色、アバター枠、表示名、ユーザー名、guild名、参加人数、日付、任意テキスト、装飾図形を追加・編集・削除。
- 各要素をマウス/タッチでドラッグ移動、角ハンドルで拡大縮小、回転、重なり順変更、整列、複製、ロック、削除。位置・寸法・回転・フォント・色・透明度を数値入力でも調整可能にする。
- 画像要素の配置は固定座標だけでなく、キャンバスサイズに対する正規化座標（0〜1）で保存し、解像度が変わっても比率を保つ。
- 右側またはサイドパネルにプロパティ編集、レイヤー一覧、Undo/Redo、ズーム、テンプレート、保存状態を設ける。ブラウザ上のライブプレビューとBot側の最終画像描画結果の差を小さくする。
- フォントや画像は許可リスト・サイズ制限を設け、外部URL画像はSSRF対策（許可スキーム、DNS/IP検査、redirect制限、timeout、サイズ上限）を行う。可能ならアップロードを推奨。
- テンプレートを初期提供し、ユーザーが複製して編集可能にする。
- サーバー側でPillow等を用いてカードを描画し、Discordに画像添付で送る。CanvasのJSONスキーマをバージョン管理し、安全な許可要素のみを描画する。
- Discordアバター等のURLはBot側で取得してキャッシュし、失敗時はフォールバック画像にする。
- 個人情報を過剰に画像へ露出させず、必要な変数だけを明示的に配置できる。

### 必須：最小実用モデレーション

- slash commandによるkick、ban、unban、timeout、timeout解除、warn、警告一覧、警告削除。理由入力は任意、対象と期間など必要パラメータを型付きで取得。
- 実行者の権限、Botの権限、対象ロール階層、guild一致、自己対象・Bot対象を検査。Discord側APIが最終権限判定者であることを前提に、失敗を安全に返す。
- 設定したmod-logチャンネルに実行者・対象・操作・理由・時刻・結果を記録。トークンやOAuth情報は絶対に記録しない。
- warnはDBに保存し、ページング可能な一覧を返す。

### 必須：ログと運用設定

- welcome/leave/mod-logチャンネル設定、役割（自動付与は初版で任意。追加する場合は権限とロール階層を検査）、タイムゾーン、言語（初期は日本語）。
- チャンネル削除、権限不足、Bot退出、guild削除・再参加に耐える。guild単位で機能を停止・再開できる。
- ヘルスチェック、構造化ログ、エラー追跡用のrequest/interaction ID、バックアップ手順。

## 4. Slash command設計

コマンド数は少なくし、対象や動作はサブコマンドと引数に集約します。コマンド名・オプション名はDiscordの制約上、英小文字のASCIIを基本にし、全てのコマンドと全てのオプションに日本語descriptionを必ず設定してください。サブコマンドにもdescriptionを設定し、コマンド一覧をREADMEに載せてください。Discordの1〜100文字制限を超えないこと。

初期案（実装前にDiscord APIの制約を確認し、合計コマンドをむやみに増やさない）：

1. `/管理`（内部名 `manage`）—「サーバーの設定確認やウェルカム機能のテストを行います」
   - `設定表示`（内部名 `show`）— 現在の主な設定を表示。
   - `welcome_test` — 指定ユーザー（任意、省略時は実行者）を使ってウェルカム画像と本文をテスト送信。
   - `leave_test` — 退出カードをテスト送信。
   - `状態`（内部名 `status`）— Bot権限、送信先、各機能状態を表示。
   日本語スラッシュ名がDiscordの現行命名ルールで利用可能か確認し、不可ならASCII名を使い、説明とローカライズを日本語化してください。

2. `/モデレーション`（内部名 `mod`）—「メンバーへの警告やタイムアウトなどの管理操作を行います」
   - `warn`：必須 `user`（対象メンバー、日本語説明）、任意 `reason`（理由、日本語説明）。
   - `timeout`：必須 `user`、必須 `duration_minutes`（期間・上限と許容値を明記）、任意 `reason`。
   - `untimeout`：必須 `user`、任意 `reason`。
   - `kick`：必須 `user`、任意 `reason`。
   - `ban`：必須 `user`、任意 `reason`、任意 `delete_message_days`（Discord APIの現行範囲に合わせる）。
   - `unban`：Discordのメンバー選択型オプションで表現できない場合はユーザーID入力を使い、対象guildのban状態を検証。
   - `warnings`：必須 `user`、任意 `page`。
   - `clear_warnings`：必須 `user`、実行前に確認ボタンを出す。
   各オプション説明を日本語で具体的に記載。操作ごとに適切なdefault_member_permissionsを設定するか、アプリ側の権限検査を必須にします。

3. `/ヘルプ`（内部名 `help`）—「利用できるコマンドと必要な権限を確認します」
   - 任意 `command`（詳細を表示するコマンド、日本語説明）。

機能をコマンドだけに詰め込んで使いづらくしないこと。画像レイアウトや複雑な設定はWeb dashboardに置き、コマンドは状態確認・テスト・即時モデレーションに絞ります。テスト対象ユーザーへの通知や実害のある操作は権限と確認を適切に扱います。

## 5. Web画面構成

1. ログイン／トップ：Discordでログイン、機能概要、プライバシー説明。
2. guild選択：guildアイコン・名前・Bot導入状態・管理可能かをカード表示。
3. guildダッシュボード：Bot接続状態、設定の不足、最近のイベント、各機能へのナビゲーション。
4. ウェルカム設定：有効/無効、投稿チャンネル、本文テンプレート、メンション設定、カードエディタ、プレビュー、テスト送信。
5. 退出設定：同様のカードエディタ、退出変数の説明、プレビュー。
6. モデレーション設定：ログチャンネル、warn一覧・ページング、基本設定。
7. 監査／設定履歴：変更者、変更時刻、変更項目。OAuthトークンや秘密情報は表示しない。
8. guild共通設定：言語、タイムゾーン、機能ごとの有効化、Bot招待リンク。

デスクトップとスマートフォンで利用可能にし、フォームの入力検証、保存中/保存済み、エラーの具体的な日本語表示、キーボード操作、スクリーンリーダー向けラベルを実装します。ダッシュボードはguild IDをURLに含める場合でも全APIで認可を再確認します。

## 6. データベース設計

PostgreSQLを前提に、UUID等の内部主キーとDiscord snowflake ID（安全のため文字列またはBIGINT。JavaScriptで精度を失わないようAPIでは文字列にする）を区別し、外部キー・ユニーク制約・インデックス・時刻列を設計してください。最低限、以下を実装します。

- `users`: id, discord_user_id unique, username/display_name/avatar等の最小プロフィール, created_at, updated_at。
- `oauth_credentials` または安全なサーバー側credential store: user_id, access_token暗号化値, refresh_token暗号化値, expires_at, scopes, updated_at。保存しない設計を選べるなら短命セッションで運用し、不要なrefresh tokenを保持しない。平文保存禁止。
- `web_sessions`: セッションIDのハッシュ、user_id、expires_at、created_at、last_seen_at。HttpOnly/Secure/SameSite Cookie。Redisを使う場合はセッションの単一ソースを明記。
- `guilds`: discord_guild_id unique, name/icon cache, bot_present, last_seen_at, created_at, updated_at。
- `guild_memberships`または必要最小限の認可キャッシュ: user_id, guild_id, permission snapshot, checked_at, expires_at。認可の唯一の根拠にしない。
- `guild_settings`: guild_id unique, locale, timezone, feature flags, welcome/leave/mod-log channel IDs, mention policy, version, updated_by, updated_at。
- `welcome_configs`: guild_id, event_type(join/leave), enabled, channel_id, message_template, card_document JSONB, schema_version, updated_by, updated_at。guild_id + event_type unique。
- `card_templates`: owner/guild scope, name, event_type, document JSONB, schema_version, created_at, updated_at。
- `warnings`: id, guild_id, target_discord_user_id, moderator_discord_user_id, reason, created_at, deleted_at, deleted_by。秘密・不要な本文を保存しない。
- `audit_logs`: guild_id, actor_discord_user_id, action, target, changed_fields JSONB（秘密値は含めない）, created_at, request_id。
- `idempotency_keys`またはdelivery logs: Discordイベントの重複処理を抑止する必要に応じて導入し、有効期限・重複制約を設定。

すべてのguild設定クエリにguildスコープを適用します。migrationを提供し、初回起動時の自動DDL生成を本番で行わず、Alembic適用手順を用意します。

## 7. API設計

REST APIは `/api/v1` 配下、JSON、Pydantic入力/出力モデル、OpenAPIを使います。エラー形式は一貫させ、内部例外や秘密情報を返さないこと。

- `GET /auth/discord/login`、`GET /auth/discord/callback`、`POST /auth/logout`、`GET /api/v1/me`。
- `GET /api/v1/guilds`：OAuthで見えるguildとBot状態を返す。管理権限を確認。
- `GET /api/v1/guilds/{guild_id}`：認可後のguild概要。
- `GET/PUT /api/v1/guilds/{guild_id}/settings`：guild設定取得・更新。
- `GET/PUT /api/v1/guilds/{guild_id}/welcome/{event_type}`：join/leave設定とカードJSON。
- `POST /api/v1/guilds/{guild_id}/welcome/{event_type}/preview`：ダミーデータでPNGプレビュー生成。Discord送信をしない。
- `POST /api/v1/guilds/{guild_id}/welcome/{event_type}/test-send`：権限者が選択チャンネルへテスト送信。
- `GET/POST/PUT/DELETE /api/v1/guilds/{guild_id}/templates`：guildテンプレートCRUD。
- `GET /api/v1/guilds/{guild_id}/warnings`：認可・フィルタ・ページング。
- `GET /api/v1/guilds/{guild_id}/audit-logs`：認可・ページング。
- `GET /health/live`、`GET /health/ready`：秘密情報を返さないreadiness/liveness。

全APIで認証、guild認可、CSRF（Cookie認証の変更系）、入力サイズ、ページング、rate limit、監査ログを一貫して適用します。`guild_id`、`channel_id`は文字列で扱い、guild所有者/Manage Guild権限をOAuth一覧またはBot Gatewayキャッシュだけで信頼しないでください。認可状態を操作時点でDiscord API等により再確認し、API障害時に安全側へ倒します。

## 8. セキュリティ・プライバシー

- Bot token、OAuth client secret、DB URL、cookie secretは環境変数またはデプロイ環境のsecret managerから読み込み、Gitに入れない。`.env`はignoreし、`.env.example`に値の例だけ置く。
- OAuth stateを暗号学的乱数で生成し、セッションに結び、callbackで一度限り検証。redirect URIは完全一致の許可リスト。PKCEがDiscordの対象フローでサポートされる場合は有効化。
- HTTPS必須。CookieはSecure/HttpOnly/SameSite=Lax以上。セッション固定対策、期限、ログアウト時失効、CSRF token、CORSの厳格な許可元、CSP/セキュリティヘッダを実装。
- OAuth tokenを保存するならアプリケーション鍵で暗号化し、鍵ローテーション手順を用意。アクセスログ・例外・監査にtoken、Authorization header、cookie、秘密情報を出さない。
- OAuth認証成功とguild管理権限は別に検証する。ユーザーが実行時にguildから権限を失った場合は即時に拒否する。IDOR対策として、全guildリソースを毎回認可する。
- 設定JSONを厳密に検証し、許可しないURL scheme、任意HTML/JS、ファイルパス、任意フォント読み込みを禁止。画像を再エンコードし、MIME偽装・巨大画像・圧縮爆弾を制限。
- SSRF、XSS、SQL injection、CSRF、クリックジャッキング、オープンリダイレクト、ログインCSRF、権限昇格、mass assignment、rate abuseを脅威モデルに含める。
- API/Webhook/プレビューにrate limitとサイズ上限。アップロードは許可形式・容量制限・保存期限を設け、可能ならオブジェクトストレージのprivate bucketを使う。
- 最小権限のBot権限を提示する。典型的にはView Channels、Send Messages、Attach Files、Embed Links、Moderate Members、Kick Members、Ban Members等を機能ごとに説明し、使わない権限は要求しない。
- moderation操作前に実行者・Bot双方の権限とロール階層を検査し、誤操作を防止。Discord応答で拒否された場合は成功扱いにしない。
- データ最小化、保持期間、ユーザーのデータ削除窓口、バックアップ削除方針、プライバシーと利用規約の雛形をREADMEに記載。
- Discord Developer Policy/TermsとAPI rate limitに準拠し、自己Bot、ユーザーアカウント操作、無断メッセージ収集を実装しない。

## 9. 推奨アーキテクチャ

単一リポジトリで、Web API、Bot Gateway worker、画像描画、共通domain/service、DBを責務分離します。初期運用のために過剰なマイクロサービス化は避けます。WebとBotは別プロセスとして起動可能にし、同じアプリケーションコード・DBを共有します。

例：

```text
src/app/
  api/                 # FastAPI routes, dependencies, schemas
  auth/                # OAuth, sessions, guild authorization
  bot/                 # discord.py client, cogs, events, commands
  cards/               # card schema, validation, renderer, fonts
  domain/              # use cases and policies
  db/                  # models, session, repositories, migrations
  security/            # crypto, csrf, rate limit, validation
  config.py
  logging.py
frontend/              # dashboard and visual card editor (if separate)
tests/
docker-compose.yml
Dockerfile
pyproject.toml
alembic.ini
README.md
```

Discordイベント処理は短時間でDB状態を読み、描画・送信失敗を構造化ログに残します。大規模化時にqueueを追加可能な境界を設けます。重複イベント・再接続・再起動に耐え、設定キャッシュはTTLと無効化方針を持たせます。

## 10. テストと品質

以下のテストコードと品質設定を実装し、利用可能なターミナルで実行してください。実行できない場合は理由を明記してください。

- unit: 権限判定、テンプレート変数、カードJSON検証、座標正規化、画像描画、警告ページング。
- API integration: OAuth callback state検証、guild認可、guild間IDOR拒否、CSRF、設定CRUD、プレビュー、rate limit。
- Bot tests: Discord依存を境界でmockし、join/leaveの有効/無効・重複・送信権限不足、moderation権限拒否と成功結果を確認。
- DB tests: Alembic migration、制約、guildデータ分離。
- frontend tests: エディタ要素の追加・ドラッグ・サイズ変更・undo/redo・保存/再ロード・APIエラー。
- e2e: docker composeで起動、OAuthを除くローカル開発モードでログイン、guild設定、カードプレビューまで一連を確認。OAuth実連携の手動確認手順も記載。
- lint/format/typecheck（例 Ruff、mypy/pyright、frontend typecheck）と脆弱性のある依存確認を実施。
- Discord本番APIに破壊的操作を行うテストを実行しない。テスト用guildと明示的な環境変数がある場合のみ手動統合テスト可能にする。

テストが失敗したら原因を分析し、コードを修正して関連テストを再実行します。Discord OAuth等の外部資格情報が必要な確認は、必要な理由とユーザーが行う手動確認手順を明記します。

## 11. デプロイ・運用

- Dockerfileは非rootユーザー、固定依存、healthcheck、適切なsignal処理を備える。開発用`docker-compose.yml`でWeb、Bot、PostgreSQL（必要に応じRedis）を起動できる。
- WebとBot workerを別サービスとして運用できる。Web複数台では共有DB/Redisセッションを使い、Bot Gatewayの同一tokenを複数プロセスで不用意に起動しない。
- `.env.example`、DB migration、初期セットアップ、Discord Developer Portal設定、OAuth redirect URL、Bot招待、privileged intent有効化、DNS/HTTPS/リバースプロキシ、バックアップ/復元をREADMEに日本語で説明。
- productionではdebug無効、TLS終端、信頼proxy設定、secret manager、DB接続pool、ログrotate、DBバックアップ、監視/アラートを設定可能にする。
- デプロイ後の確認手順（health、OAuthログイン、guild選択、カードpreview、テスト送信、join/leave、権限不足表示）をチェックリスト化。
- graceful shutdown時にDB接続・Bot接続を閉じる。再起動後に設定を復元し、必要ならDiscord command syncを開発時guild限定、本番は起動のたびに無制限再登録しない形にする。

## 12. 実装フェーズと各フェーズの完了条件

### Phase 1: ワークスペース調査と実行基盤

ワークスペース、既存コード、実行環境を調査し、構成決定、設定管理、DB接続、migration、ログ、Docker Compose、READMEを実装。開発環境でWeb/workerが起動しhealth endpointが返ることを確認する。

### Phase 2: OAuthとguild認可

Discord OAuth2、セッション、guild一覧、Bot参加状態、管理権限検証、guild dashboardを実装。未認可guildのGET/PUTが拒否される。

### Phase 3: カードエディタ縦切り

カードJSONスキーマ、フロント編集、ドラッグ/自由配置、プレビューAPI、サーバー描画、設定保存/再読み込みまでを一連で完成。実ブラウザ上で編集結果が描画される。

### Phase 4: Discord Botイベントと送信

join/leave、本文変数、画像添付、権限不足、イベント重複対策、テスト送信を実装。無効設定では送信せず、有効設定で指定チャンネルへ送る。

### Phase 5: Slash commandとモデレーション

少数のコマンド、すべての説明の日本語化、権限・階層チェック、warn DB、mod-log、失敗応答を実装。コマンドsync手順を用意。

### Phase 6: セキュリティ・品質・運用仕上げ

テスト、lint/typecheck、脅威対策、スマートフォン対応、アクセシビリティ、バックアップ・復元、production設定を完成し、全体を再確認する。

フェーズを省略したり、雛形だけ作って終わらせたりしないでください。各フェーズは「機能がワークスペースに実装され、エラーが適切に扱われ、テストとREADMEが含まれる」状態で完了とします。実行していない検証を実行済みと表現してはいけません。

## 13. 受け入れ基準（すべて満たす）

1. READMEどおりにローカルで依存サービスとアプリを起動でき、health endpointが成功する。
2. DB migrationを新規DBへ適用できる。設定保存後の再起動でも設定が保持される。
3. Discord OAuthログイン後、管理可能かつBot導入済みのguildを選択して設定できる。無権限guildへのアクセスは拒否される。
4. welcome/leaveカードをブラウザで追加・移動・拡大縮小・回転・保存・再読込でき、プレビューPNGが得られる。
5. Botがjoin/leaveでguild別の設定を使い、画像とメッセージを指定チャンネルへ送る。無効時、権限不足時、設定不備時に安全に振る舞う。
6. テスト送信は実際のDiscord送信、通常プレビューは副作用のない画像生成として区別される。
7. slash commandと全optionに短く明確な日本語説明があり、コマンド数は少数に抑えられている。
8. moderation操作は権限・階層検証があり、warnと監査ログが保存される。エラーを成功と誤表示しない。
9. tokenやsecretがソース、ログ、HTTPレスポンスに露出しない。CSRF、IDOR、OAuth state、SSRF、アップロード制限をテストしている。
10. 自動テスト、lint、型検査、フロントビルドが通る。未実行項目は理由を正確に記録する。
11. 他guildへの展開でguild設定が相互に漏れず、必要なOAuth、Bot権限、Developer Portal設定がREADMEに明記されている。
12. 最終報告に完成した機能、主要ファイル、起動方法、環境変数、実行した検証、外部資格情報が必要な手動確認を列挙する。

## 14. 最終作業指示

まずワークスペースを調査して実装計画を示し、Phase 1〜6を順に進めてください。見た目だけの画面やplaceholderで受け入れ基準を満たしたと主張してはいけません。Discord OAuthやBot tokenが未設定でも、開発者が値を設定すれば運用できるコード経路を実装し、未設定時には設定不足を日本語で説明してください。必要なコード、migration、frontend、テスト、Docker、READMEをワークスペースに作成・更新してください。最後に変更ファイル、起動方法、必要な環境変数、実行した検証と結果、外部資格情報が必要で未実施の確認を報告してください。
