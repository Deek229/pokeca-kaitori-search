@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 全店舗 買取価格取込 — SV9 テスト（フルコンプ + カードラッシュ）
echo ※ メルカードは通販休業中（503）のためスキップ。
python tools\fetch_shop_prices.py --shop all --set SV9 --refresh
pause
