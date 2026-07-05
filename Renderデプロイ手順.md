# ポケカ買取価格サーチ — Render デプロイ手順

非エンジニア向けの手順です。  
**ローカルで動いている状態**（`起動.bat` で http://127.0.0.1:8053 が開ける）を前提にしています。

---

## このサイトを Render に載せると

- インターネット上の URL で誰でも検索できます
- GitHub にコードを置くと、更新のたびに自動で再デプロイできます
- **価格データは SQLite（`data/cards.db`）に入っています**

---

## 重要：データベース（SQLite）について

| 方式 | 説明 | おすすめ |
|------|------|----------|
| **A. DB を Git に含める（無料プラン）** | ローカルで取り込んだ `cards.db` をリポジトリにコミット。Render はそのファイルを読むだけ | **まずはこれ** |
| **B. Render 永続ディスク（有料）** | `render.yaml` の `disk` を有効化。再デプロイしても DB が消えない | 本番運用で価格をサーバー上で更新したい場合 |
| **C. 空の DB で起動** | DB なしだとカードがほぼ表示されない | 非推奨 |

**ビルド時に価格取得スクリプトは動きません**（アニメサイトの seed 問題を避けるため）。  
価格を更新したら **ローカルで取込 → `cards.db` を GitHub に push** してください。

---

## 手順 1：GitHub にリポジトリを作る

1. ブラウザで https://github.com にログイン（アカウント: **Deek229** など）
2. 右上 **＋** → **New repository**
3. 設定例  
   - Repository name: `pokeca-kaitori-search`（任意）  
   - Public  
   - **README は追加しない**（空のリポジトリ）
4. **Create repository** をクリック
5. 表示された URL をメモ（例: `https://github.com/Deek229/pokeca-kaitori-search.git`）

---

## 手順 2：PC から GitHub に初回アップロード

エクスプローラーで `13_ポケカ買取価格サーチ` を開き、PowerShell で:

```powershell
cd "C:\Users\a_n_k\OneDrive\Desktop\CORSOR　プロジェクト\13_ポケカ買取価格サーチ"

git init
git add .
git status
```

**確認:** `.env` や `data/probe*.html` などは含まれず、`data/cards.db` が含まれていること。

```powershell
git commit -m "Initial deploy: FastAPI + SQLite for Render"
git branch -M main
git remote add origin https://github.com/Deek229/pokeca-kaitori-search.git
git push -u origin main
```

※ GitHub のログインを求められたら、ブラウザまたは Personal Access Token で認証します。

---

## 手順 3：Render で Web サービスを作る

### 方法 A：Blueprint（おすすめ・`render.yaml` 使用）

1. https://dashboard.render.com にログイン
2. **New +** → **Blueprint**
3. 手順 2 で作った GitHub リポジトリを接続
4. `render.yaml` の内容が表示される → **Apply**
5. デプロイ完了まで 5〜10 分待つ

### 方法 B：手動で Web Service

1. **New +** → **Web Service**
2. リポジトリを選択
3. 次のように設定  

| 項目 | 値 |
|------|-----|
| Name | `pokeca-kaitori-search` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |

4. **Advanced** → Environment Variables  

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.12.0` |
| `SITE_URL` | デプロイ後の URL（例: `https://pokeca-kaitori-search.onrender.com`） |

5. **Create Web Service**

---

## 手順 4：動作確認

1. Render の **Logs** で `Application startup complete` を確認
2. ブラウザで表示された URL を開く（例: `https://pokeca-kaitori-search.onrender.com`）
3. 検索・カード詳細・価格がローカルと同様に見えるか確認
4. `https://（あなたのURL）/api/health` で `{"status":"ok",...}` が返るか確認

---

## 本番での「起動.bat」に相当すること

| ローカル（Windows） | Render（本番） |
|---------------------|----------------|
| `起動.bat` をダブルクリック | 常時起動（手動操作不要） |
| ポート 8053 | Render の `$PORT`（自動） |
| DB なし → `seed.py` 実行 | **実行しない**（同梱の `cards.db` を使用） |
| 価格取込バッチ | **ローカルで実行** → `cards.db` を push |

**価格の更新手順（本番反映）**

1. ローカルで `全店舗価格取込.bat` などを実行
2. `git add data/cards.db`
3. `git commit -m "Update buyback prices"`
4. `git push`
5. Render が自動再デプロイ（数分）

---

## 無料プランの注意

- **15 分アクセスがないとスリープ** → 初回アクセスで 30 秒ほど起動待ち
- **再デプロイのたびにファイルシステムは初期化**される（永続ディスク未使用時）  
  → DB は Git 同梱方式（A）か永続ディスク（B）が必須
- シークレット（API キー等）は **Environment Variables** にのみ設定（`.env` は Git に入れない）

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| カードがほとんど出ない | `data/cards.db` が Git に含まれているか確認。ローカルで `全カード取込.bat` 後に再 push |
| 502 / 起動失敗 | Render Logs を確認。`pip install` 失敗なら `requirements.txt` を確認 |
| 価格が古い | ローカルで価格取込 → `cards.db` を commit & push |
| サイトが遅い | 無料プランのスリープ。有料プランまたは外部 ping で緩和可 |

---

## 関連ファイル

| ファイル | 役割 |
|----------|------|
| `render.yaml` | Render の自動設定 |
| `.env.example` | 環境変数の例（本番は Render ダッシュボードで設定） |
| `config.py` | `SITE_URL` / `PORT` の読み取り |
| `data/cards.db` | カード・価格データ（Git 同梱推奨） |

ローカル開発は従来どおり **`起動.bat`** をご利用ください。
