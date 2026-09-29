#!/usr/bin/env bash
set -e
cd ~/botshop

echo "🔧 BotShop 修復 + 重新上線"
echo "════════════════════════"
echo ""

# 1. 停掉 root cloudflared（避免跟 quick tunnel 衝突）
if systemctl is-active --quiet cloudflared; then
    echo "🛑 停掉系統 cloudflared service…"
    sudo systemctl stop cloudflared || true
    sudo systemctl disable cloudflared 2>/dev/null || true
fi

# 2. 殺掉所有殘留 process
echo "🧹 清掉舊 process…"
sudo pkill -f '/usr/local/bin/cloudflared' 2>/dev/null || true
pkill -f 'cloudflared tunnel' 2>/dev/null || true
pkill -f 'python app.py' 2>/dev/null || true
sleep 2

# 3. 確認 cloudflared 有裝
if ! command -v cloudflared >/dev/null 2>&1; then
    echo "📥 裝 cloudflared…"
    curl -L -s https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
    chmod +x /tmp/cloudflared
    sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

# 4. 啟動網站
echo "🚀 啟動網站…"
source .venv/bin/activate
nohup python app.py > /tmp/botshop-web.log 2>&1 &
WEB_PID=$!
echo "   PID: $WEB_PID"
sleep 3

if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q 200; then
    echo "❌ 網站沒起來，看 log:"
    tail -30 /tmp/botshop-web.log
    exit 1
fi
echo "   ✅ 網站回應 200"

# 5. 啟動 quick tunnel
echo "🌐 啟動 Cloudflare Tunnel…"
nohup cloudflared tunnel --url http://localhost:5000 --no-autoupdate > /tmp/botshop-tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "   PID: $TUNNEL_PID"

# 6. 等 URL
echo ""
echo "⏳ 等 Cloudflare 分配網址（最多 90 秒）…"
URL=""
for i in $(seq 1 90); do
    sleep 1
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/botshop-tunnel.log 2>/dev/null | head -1 || true)
    [ -n "$URL" ] && break
    printf "."
done
echo ""

if [ -z "$URL" ]; then
    echo "❌ 沒拿到 URL，tunnel log:"
    tail -40 /tmp/botshop-tunnel.log
    exit 1
fi

# 7. 驗證 URL（等它生效）
echo "🔍 驗證 $URL …"
sleep 5
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time 15 || echo "fail")

echo ""
echo "════════════════════════════════"
if [ "$CODE" = "200" ]; then
    echo " ✅ 上線成功！"
else
    echo " ⚠️ 拿到 URL 但回應 $CODE（可能還要等一下）"
fi
echo "════════════════════════════════"
echo ""
echo "🌐 網站：  $URL"
echo "🔧 後台：  $URL/admin"
echo "🔑 密碼：  botshop_admin"
echo ""
echo "📄 Log："
echo "   /tmp/botshop-web.log"
echo "   /tmp/botshop-tunnel.log"
echo ""
