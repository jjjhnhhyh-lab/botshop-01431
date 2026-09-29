#!/usr/bin/env bash
set -eo pipefail   # 拿掉 -u，避免 unbound 炸

cd "$HOME/botshop"

echo ""
echo "════════════════════════════"
echo "  BotShop 設定"
echo "════════════════════════════"
echo ""

read -rp "① Discord Bot Token          : " DC_TOKEN
read -rp "② Supabase DATABASE_URL      : " DB_URL
read -rp "③ Pterodactyl 網址 (https://): " PTERO_URL
read -rp "④ Pterodactyl Client API Key : " PTERO_KEY
read -rp "⑤ Pterodactyl Server UUID    : " PTERO_SERVER
read -rsp "⑥ 管理後台密碼               : " ADMIN_PW; echo ""

SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")

cat > .env <<EOF
SECRET_KEY=$SECRET
ADMIN_PASSWORD=$ADMIN_PW
DATABASE_URL=$DB_URL
PTERO_URL=$PTERO_URL
PTERO_KEY=$PTERO_KEY
PTERO_SERVER=$PTERO_SERVER
EOF

cat > bot.env <<EOF
DATABASE_URL=$DB_URL
DISCORD_TOKEN=$DC_TOKEN
EOF

chmod 600 .env bot.env
echo "✅ .env 已寫入"

echo ""
echo "📦 建立 venv + 裝依賴…"
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ 依賴裝好了"

echo ""
echo "🗄️  建立 Supabase 資料表…"
python3 - <<'PYDB'
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
sql = open("schema.sql", encoding="utf-8").read()
with psycopg2.connect(os.environ["DATABASE_URL"]) as c:
    with c.cursor() as cur:
        cur.execute(sql)
print("✅ 資料表建立完成")
PYDB

echo ""
echo "════════════════════════════"
echo " ✅ 全部處理完成"
echo "════════════════════════════"
echo ""
echo "本機測試："
echo "  cd ~/botshop && source .venv/bin/activate && python app.py"
echo ""
echo "部署到 Koyeb："
echo "  1. 到 ~/botshop 執行 git init && git add . && git commit -m init"
echo "  2. 推上 GitHub，Koyeb 拉 repo"
echo "  3. Build: pip install -r requirements.txt"
echo "  4. Run:   gunicorn app:app --bind 0.0.0.0:\$PORT"
echo "  5. 環境變數貼 .env 內容"
echo ""
