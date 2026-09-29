#!/usr/bin/env bash
set -e
cd ~/botshop

echo "🚀 BotShop 部署腳本"
echo "════════════════════"
echo ""

# .gitignore
cat > .gitignore <<'GITIGNORE'
.venv/
.env
bot.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
GITIGNORE

# 檢查 gh CLI
if ! command -v gh >/dev/null 2>&1; then
    echo "📥 安裝 GitHub CLI…"
    sudo apt update -qq
    sudo apt install -y gh
fi

# 檢查登入
if ! gh auth status >/dev/null 2>&1; then
    echo ""
    echo "🔐 需要用 GitHub 登入（等等會開瀏覽器）"
    echo "   選擇：GitHub.com → HTTPS → Login with a web browser"
    echo ""
    gh auth login --web --git-protocol https
fi

# git init
if [ ! -d .git ]; then
    git init -q
    git branch -M main 2>/dev/null || true
fi

git config user.email "botshop@local" >/dev/null 2>&1 || true
git config user.name "BotShop" >/dev/null 2>&1 || true

# commit
git add -A
git diff --cached --quiet || git commit -q -m "init botshop"

# 建 repo（用隨機後綴避免重複）
REPO_NAME="botshop-$(date +%s | tail -c 6)"

if ! gh repo view "$REPO_NAME" >/dev/null 2>&1; then
    echo "📦 建立 GitHub repo：$REPO_NAME"
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
else
    git push -u origin main 2>/dev/null || true
fi

REPO_URL=$(gh repo view --json url -q .url)

echo ""
echo "════════════════════════════════════════════"
echo " ✅ GitHub 完成"
echo "════════════════════════════════════════════"
echo ""
echo "🌐 Repo：$REPO_URL"
echo ""
echo "────────────────────────────────────────────"
echo " 下一步：部署到 Koyeb（免費、永久 URL）"
echo "────────────────────────────────────────────"
echo ""
echo "1. 開 https://app.koyeb.com"
echo "2. 點「Sign up」→ 選「Continue with GitHub」"
echo "3. 授權 Koyeb 讀取你的 repo"
echo "4. 首頁點「Create Service」→ 選「GitHub」"
echo "5. 選剛剛建的 repo：$REPO_NAME"
echo "6. 設定："
echo "     Builder:        Buildpack"
echo "     Run command:    gunicorn app:app --bind 0.0.0.0:8000"
echo "     Port:           8000"
echo "     Instance:       Free (nano)"
echo "     Region:         Singapore"
echo "7. 環境變數（從 ~/botshop/.env 抄）："
echo "     SECRET_KEY      = (從 .env 抄)"
echo "     ADMIN_PASSWORD  = botshop_admin"
echo "     SUPABASE_URL    = https://usxtvbnvduungvsmnpml.supabase.co"
echo "     SUPABASE_KEY    = sb_publishable_kZkiD0to8bChHXWqoJvoGA_3xuSVBUm"
echo "     PTERO_URL       = http://127.0.0.1"
echo "     PTERO_KEY       = ptlc_fLuwnugG4ChqePcgFr2sqq8ghCMROAMp7duBkhUEk0u"
echo "8. 按「Deploy」"
echo ""
echo "2-3 分鐘後 Koyeb 給你永久 URL：https://xxx.koyeb.app"
echo ""
