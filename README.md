# ポケカ買取価格サーチ



ポケモンカードの**買取価格**を、主要ショップ4社分まとめて比較できるWebサイト（MVP）です。



## できること（MVP）



- カード名・番号で検索（キーワード検索は50件ずつページ送り。セットのみの絞り込みは全件表示）

- 4ショップ（カードラッシュ / メルカード / フルコンプ / **Magi**）の価格を横並び表示（未取得は **—**）

- Magi は **C2C 最安出品価格（参考）**、他店は買取価格

- 価格の「更新日」を表示

- **価格推移グラフ**（履歴2件以上で表示。ショップ別の線 + **全店平均**の破線。同日の再取得も別点として表示）

- TCGdex から取り込んだ全カード（約6,000枚超）に対応



> カードラッシュは **cardrush.media** の新買取表から自動取得可能（2026-06 調査）。**メルカードは通販サイト休業中（503）のため自動取得を一時停止**（カード詳細では検索リンクのみ）。フルコンプ・カードラッシュは `fetch_shop_prices.py` で全カード（約6,143枚）に対応。Magi は `fetch_magi_prices.py` で参考価格を取得できます。

詳細: [カードラッシュ・メルカード調査](docs/カードラッシュメルカード調査.md)



---



## 初回セットアップ（Windows）



### 1. フォルダを開く



エクスプローラーでこのフォルダを開きます。



```

13_ポケカ買取価格サーチ

```



### 2. Python を確認



コマンドプロンプトまたは PowerShell で:



```bat

python --version

```



`Python 3.10` 以上が表示されればOKです。  

未インストールの場合は [python.org](https://www.python.org/downloads/) からインストールしてください（「Add Python to PATH」にチェック）。



### 3. 必要な部品をインストール



```bat

cd 13_ポケカ買取価格サーチ

pip install -r requirements.txt

```



### 4. サンプルデータを入れる



```bat

python tools\seed.py

```



「シード完了」と表示されれば成功です（ショップ情報と人気カード15枚の買取価格サンプル）。



### 5. 全カードマスタを取り込む（推奨）



TCGdex から**日本語の全セット・全カード**を DB に投入します。  

買取価格は入れません（サンプル15枚の価格だけ残ります）。



**方法A:** `全カード取込.bat` をダブルクリック



**方法B:** コマンドで実行



```bat

python tools\fetch_all_tcgdex.py --resume

```



- 初回は **約3〜5分**（セット約170件・カード約1.5万枚）

- 途中で止まっても、同じコマンドで**続きから再開**できます

- 最初からやり直す: `python tools\fetch_all_tcgdex.py --force`



### 6. Magi 参考価格を取得（任意・全カード）



Magi（[magi.camp](https://magi.camp/)）は C2C マーケットのため**買取価格は公開されていません**。  

出品中の**最安価格**を参考値として取得・保存します。



**方法A:** `Magi価格取込.bat` をダブルクリック



**方法B:** コマンドで実行



```bat

python tools\fetch_magi_prices.py --resume

```



| 項目 | 内容 |

|------|------|

| データソース | `https://magi.camp/items/search.json`（出品一覧 API） |

| 保存先 | `buyback_prices`（当日スナップショット）+ `price_history`（履歴） |

| 推定時間 | 約6,000枚 × 1秒間隔 ≒ **100分**（`--delay` で変更可） |

| 再開 | `--resume` で中断位置から続行 |

| 最初から | `--force` |

| テスト（10枚） | `python tools\fetch_magi_prices.py --limit 10` |



**マッチング:** カード名 + セット略称で Magi を検索し、出品名・カード番号の一致スコアで最安出品を採用。詳細は `tools/fetch_magi_prices.py` 先頭コメント参照。



**既存DBの Magi 表示名修正:**



```bat

python tools\seed.py --migrate

```



「マギ」→「Magi」に更新し、不足ショップ・サンプル価格も追加します。



### 6b. 買取価格を取得（フルコンプ / カードラッシュ）



**方法A:** `全店舗価格取込.bat`（**全カード・推奨**）または `全店舗価格取込_SV9.bat`（SV9 テスト）



**方法B:** コマンドで実行



```bat

python tools\fetch_shop_prices.py --shop all --all --refresh

python tools\fetch_shop_prices.py --shop fullcomp --all --refresh

python tools\fetch_shop_prices.py --shop cardrush --all --refresh

```



`--shop all` は **フルコンプ + カードラッシュ**のみ実行します（メルカードは 503 のためスキップ）。



**初回・日次の使い分け**



| 状況 | コマンド / バッチ |

|------|------------------|

| **日次更新**（全カード・推奨） | `全店舗価格取込.bat` または `--shop all --all --refresh` |

| **SV9 だけテスト** | `全店舗価格取込_SV9.bat` または `--set SV9 --refresh` |

| **同日に途中で止まった** | `--resume`（本日完了済みのみスキップ） |

| **進捗を捨てて最初から** | `--force` |



```bat

# 日次（推奨）— 全カード約6,143枚を再取得し DB を更新

python tools\fetch_shop_prices.py --shop all --all --refresh

# SV9 テスト（132枚）

python tools\fetch_shop_prices.py --shop all --set SV9 --refresh

# 同日の続き

python tools\fetch_shop_prices.py --shop all --all --resume

# テスト（20枚のみ）

python tools\fetch_shop_prices.py --shop cardrush --all --limit 20

# 進捗 JSON をリセット

python tools\fetch_shop_prices.py --shop all --all --force

```



| ショップ | 自動取得 | データソース | SV9 テスト結果（2026-06） |

|---------|---------|-------------|---------------------------|

| **フルコンプ** | ✅ 可能 | 店舗買取表 HTML 内 `tableData` | **44/132（33.3%）** — 買取表に掲載があるカードのみ |

| **カードラッシュ** | ✅ 可能 | [cardrush.media](https://cardrush.media/pokemon/buying_prices) 買取表 | **55/132（41.7%）** — 旧 Google シートは `#REF!` で失效 |

| **メルカード** | ⏸ 一時停止 | mercardpokemon.jp（通販休業中） | 503 — 検索リンクのみ（`--shop mercard` で個別実行可） |



**該当なしは正常:** 買取表に載っていないカードは「該当なし」となり、価格は **—** のままです（エラーではありません）。



| 項目 | 内容 |

|------|------|

| 対象カード数 | DB 内の全カード（現在 **約6,143枚**） |

| 保存先 | `buyback_prices` + `price_history` |

| 推定時間（全カード） | フルコンプ **約10〜30秒**（買取表1回 + マッチング） / カードラッシュ **約5〜7分**（買取表119ページ + マッチング） / 合計 **約6〜8分** |

| 推定時間（SV9 132枚） | フルコンプ **約5秒** / カードラッシュ **約1〜2分** |

| **日次更新** | `--refresh`（バッチ既定）— 毎回全カード再取得 |

| 同日の続き | `--resume` — 本日完了済みのみスキップ |

| 最初から | `--force` — 進捗 JSON をリセット |

| 1店のみ | `--shop fullcomp` / `cardrush` / `mercard` |

| 進捗ファイル | `data/{shop}_price_fetch_progress.json` |



個別バッチ: `フルコンプ価格取込.bat` / `カードラッシュ価格取込.bat` / `メルカード価格取込.bat`



### 7. サイトを起動



```bat

python -m uvicorn app:app --reload --port 8053

```



または **`起動.bat`** をダブルクリック。



### 8. ブラウザで開く



```

http://127.0.0.1:8053

```



カード詳細例（グラフは履歴2件以上で表示）:



```

http://127.0.0.1:8053/cards/sv9_033

```



---



## よく使うコマンド



| やりたいこと | コマンド |

|-------------|---------|

| サンプルデータ再投入（**TCGdex 取込データも削除**） | `python tools\seed.py --reset` |

| 既存DBに新ショップ追加・Magi名修正 | `python tools\seed.py --migrate` |

| **全カード一括取込** | `全カード取込.bat` または `python tools\fetch_all_tcgdex.py --resume` |

| **Magi 参考価格一括取得** | `Magi価格取込.bat` または `python tools\fetch_magi_prices.py --resume` |

| **3店舗 買取価格（全カード）** | `全店舗価格取込.bat` または `python tools\fetch_shop_prices.py --shop all --all --refresh` |

| **3店舗 買取価格（SV9 テスト）** | `全店舗価格取込_SV9.bat` または `python tools\fetch_shop_prices.py --shop all --set SV9 --refresh` |

| **フルコンプのみ（全カード）** | `フルコンプ価格取込.bat` または `python tools\fetch_shop_prices.py --shop fullcomp --all --refresh` |

| **カードラッシュのみ（全カード）** | `カードラッシュ価格取込.bat` または `python tools\fetch_shop_prices.py --shop cardrush --all --refresh` |

| Magi 取得テスト（10枚） | `python tools\fetch_magi_prices.py --limit 10` |

| 取込を最初からやり直す | `python tools\fetch_all_tcgdex.py --force` / `python tools\fetch_magi_prices.py --force` / `python tools\fetch_shop_prices.py --force` |

| TCGdex から1セット取得（動作確認） | `python tools\fetch_tcgdex_set.py SV9` |



---



## 価格推移グラフ



- DB テーブル `price_history` に取得のたび価格を**追記**（上書きしない）

- `buyback_prices` は各ショップの**最新スナップショット**（比較表用）

- カード詳細ページ `/cards/{card_id}` で Chart.js 折れ線グラフを表示

- **履歴が2件以上**あればグラフ表示（**同日の再取得**も別の点として表示）

- 履歴1件のとき: 「あと1回取込するとグラフ表示（全店平均の破線含む）」メッセージ

- **ショップ別の線:** カードラッシュ=黄 / フルコンプ=緑 / メルカード=青 / Magi=紫（参考）

- **全店平均（破線）:** その日時点で価格がある**買取店舗**（Magi 参考価格を除く）の平均。店舗によって価格がない日はその店舗を平均から除外



---



## フォルダ構成



```

13_ポケカ買取価格サーチ/

├── app.py              … Webアプリ本体

├── config.py           … 設定

├── db.py               … SQLite データベース

├── card_service.py     … 検索・詳細ロジック

├── templates/          … HTML ページ

├── static/             … CSS

├── data/cards.db       … データ（seed後に作成）

├── tools/

│   ├── seed.py              … サンプルデータ投入・マイグレーション

│   ├── fetch_all_tcgdex.py  … 全セット一括取込

│   ├── fetch_magi_prices.py … Magi 参考価格一括取得

│   ├── fetch_shop_prices.py … 3店舗 買取価格一括取得

│   ├── shops/               … 店舗別取得モジュール

│   ├── fetch_tcgdex_set.py  … 1セット取込（動作確認）

│   └── tcgdex_import.py     … TCGdex 共通ロジック

├── 全カード取込.bat         … TCGdex 一括取込

├── Magi価格取込.bat         … Magi 参考価格一括取得

├── 全店舗価格取込_SV9.bat   … 3店舗 買取 SV9 テスト

├── 全店舗価格取込.bat       … 3店舗 買取 全カード

├── フルコンプ価格取込.bat   … フルコンプのみ

├── docs/MVP設計.md     … 画面・DB設計メモ

├── TCGdex調査.md       … TCGdex API 調査結果

└── README.md           … このファイル

```



---



## 関連ドキュメント



- [MVP設計（画面・DB）](docs/MVP設計.md)

- [TCGdex API 調査](TCGdex調査.md)
- [カードラッシュ・メルカード 買取取得調査](docs/カードラッシュメルカード調査.md)



---



## 注意事項・制限



1. **Magi は参考価格** — 買取価格ではなく、個人出品の最安値です。状態・送料は出品ごとに異なります。

2. **マッチング精度** — 同名カード・略称違いで誤マッチする可能性があります。

3. **レート制限** — 既定1秒/リクエスト。短くしすぎると Magi 側でブロックされる恐れがあります。

4. **利用規約** — 大量アクセスは magi.camp の ToS に抵触する可能性があります。個人利用・適度な間隔を推奨します。

5. **他3店舗** — フルコンプ・カードラッシュは全カード自動取得可。メルカードは通販休業（503）で**一時停止**（検索リンクのみ。再開時に `--shop mercard` で個別取得可能）。



---



## トラブルシューティング



### 全カード取込後もカードが15枚のまま



**原因:** `data/tcgdex_import_progress.json` に「完了済み」と記録されている一方、`data/cards.db` が seed（15枚）だけの状態になっていると、`--resume` が**全セットをスキップ**します。



よくあるきっかけ:



- `python tools\seed.py --reset` または旧版の `seed.py` 実行で DB が初期化された

- `cards.db` を削除したあと `起動.bat` / `全カード取込.bat` が seed だけ実行した（進捗 JSON は残った）



**対処:**



```bat

python tools\fetch_all_tcgdex.py --force

```



または `全カード取込.bat` を再実行（不整合を検出すると自動で `--force` 相当の再取込を開始します）。



**確認:**



```bat

python -c "import sys; sys.path.insert(0,'.'); from tools.tcgdex_import import db_stats; print(db_stats())"

```



カード数が **1000 枚以上**（通常は 6000 枚超）になっていれば OK です。



### 価格取込で「132枚スキップ・更新 0」になる



**原因:** 旧版は `--resume` が `completed_card_ids` を**永久に**スキップしていました。一度完了すると再実行しても全カードが飛ばされ、価格が更新されません（メルカード 503 時も誤って完了扱いになることがありました）。



**対処:**



```bat

全店舗価格取込_SV9.bat

```



（内部で `--refresh` を使用。毎回全カードを再取得します）



または:



```bat

python tools\fetch_shop_prices.py --shop all --set SV9 --refresh

```



| 目的 | フラグ |

|------|--------|

| 日次更新（推奨） | `--refresh` |

| 同日に途中で止まった続き | `--resume` |

| 進捗 JSON を捨てる | `--force` |



### seed を実行したら取込データが消えた



`python tools\seed.py --reset` は意図的に全削除します。通常の `python tools\seed.py` は**既存 DB がある場合はマイグレーションのみ**（カードマスタは削除しません）。

