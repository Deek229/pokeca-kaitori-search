@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo フルコンプ 買取価格取込 — 全カード
python tools\fetch_shop_prices.py --shop fullcomp --all --refresh
pause
