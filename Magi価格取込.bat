@echo off



chcp 65001 >nul



cd /d "%~dp0"



echo ========================================

echo  Magi 参考価格 一括取込

echo ========================================

echo.

echo Magi (magi.camp) の出品最安価格を全カード分取得します。

echo ※ 買取価格ではなく C2C 参考価格です。

echo.

echo 6143枚 × 1秒間隔 ≒ 約100分。中断しても再実行で続きから再開できます。

echo.



if not exist "data\cards.db" (

    echo データベースがありません。先に seed と全カード取込を実行してください。

    pause

    exit /b 1

)



python tools\fetch_magi_prices.py --resume



echo.

echo 完了しました。起動.bat でサイトを開いてカード詳細を確認できます。

pause

