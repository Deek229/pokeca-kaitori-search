@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 全店舗 買取価格取込 — 全カード（フルコンプ + カードラッシュ）
echo ※ メルカードは通販休業中（503）のためスキップ。カード詳細では検索リンクのみ表示します。
python tools\fetch_shop_prices.py --shop all --all --refresh
pause
