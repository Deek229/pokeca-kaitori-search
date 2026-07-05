@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  ポケカ買取価格サーチ 起動
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [エラー] Python が見つかりません。
    echo Python 3 をインストールし、PATH に追加してください。
    echo.
    pause
    exit /b 1
)

if not exist "data\cards.db" (
    echo データベースがありません。seed を実行します...
    python tools\seed.py
    if errorlevel 1 (
        echo.
        echo [エラー] seed の実行に失敗しました。
        echo.
        pause
        exit /b 1
    )
    echo.
)

echo 既存のサーバー（ポート 8053）を停止しています...
for /L %%i in (1,1,3) do (
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8053" ^| findstr "LISTENING"') do (
        echo   PID %%a を停止します...
        rem /T = 子プロセス（uvicorn worker）も含めて終了
        taskkill /F /T /PID %%a >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

netstat -ano 2>nul | findstr ":8053" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] ポート 8053 がまだ使用中です。数秒待ってから再実行してください。
    echo.
    pause
    exit /b 1
)

echo.
echo ブラウザで http://127.0.0.1:8053 を開いてください
echo バトルパートナーズ全件: http://127.0.0.1:8053/search?set_id=sv9 （132件）
echo 終了するには Ctrl+C
echo.

python -m uvicorn app:app --reload --reload-dir "%~dp0." --port 8053
set UVICORN_EXIT=%ERRORLEVEL%

if not %UVICORN_EXIT%==0 (
    echo.
    echo [エラー] サーバーの起動に失敗しました ^(exit %UVICORN_EXIT%^).
    echo   - ポート 8053 が他のアプリで使われていないか確認してください
    echo   - 依存パッケージ: pip install -r requirements.txt
    echo.
    pause
    exit /b %UVICORN_EXIT%
)

endlocal
