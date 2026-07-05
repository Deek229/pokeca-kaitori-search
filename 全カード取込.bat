@echo off

chcp 65001 >nul

cd /d "%~dp0"

echo ========================================
echo  TCGdex 全カード取込
echo ========================================
echo.
echo 日本語セット・カードを TCGdex から取得して DB に保存します。
echo 買取価格は投入しません（既存のサンプル価格はそのまま残ります）。
echo.
echo 初回は数分かかります。中断した場合は再実行で続きから再開できます。
echo.

if not exist "data\cards.db" (
    echo データベースがありません。先に seed を実行します...
    python tools\seed.py
    echo.
)

echo --- 取込前 DB ---
python -c "import sys; sys.path.insert(0,'.'); from tools.tcgdex_import import db_stats; s=db_stats(); print(f'セット {s[\"sets\"]} / カード {s[\"cards\"]} / 買取価格 {s[\"buyback_prices\"]}')"
echo.

python tools\fetch_all_tcgdex.py --resume
set IMPORT_EXIT=%ERRORLEVEL%

echo.
echo --- 取込後 DB ---
python -c "import sys; sys.path.insert(0,'.'); from tools.tcgdex_import import db_stats, MIN_CARDS_WHEN_MANY_SETS_DONE; s=db_stats(); print(f'セット {s[\"sets\"]} / カード {s[\"cards\"]} / 買取価格 {s[\"buyback_prices\"]}'); sys.exit(0 if s['cards'] >= MIN_CARDS_WHEN_MANY_SETS_DONE else 1)"
set COUNT_EXIT=%ERRORLEVEL%

if %COUNT_EXIT% neq 0 (
    echo.
    echo [警告] カード数が 1000 枚未満です。
    echo DB がリセットされた、または取込がスキップされた可能性があります。
    echo 以下で最初から取り直してください:
    echo   python tools\fetch_all_tcgdex.py --force
    echo.
)

if %IMPORT_EXIT% neq 0 (
    echo 取込スクリプトがエラー終了しました ^(exit %IMPORT_EXIT%^).
)

echo.
echo 完了しました。起動.bat でサイトを開いて検索できます。
pause
