@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo メルカード 買取価格取込
python tools\fetch_shop_prices.py --shop mercard --set SV9 --refresh
pause
