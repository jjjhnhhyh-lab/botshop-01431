import os, requests
from pathlib import Path
from functools import wraps
from urllib.parse import urlencode
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")
URL           = os.environ["SUPABASE_URL"].rstrip("/")
KEY           = os.environ["SUPABASE_KEY"]
ADMIN_PW      = os.environ.get("ADMIN_PASSWORD", "admin")
PTERO_URL     = (os.environ.get("PTERO_URL") or "").rstrip("/")
PTERO_KEY     = os.environ.get("PTERO_KEY") or ""
PTERO_SERVER  = os.environ.get("PTERO_SERVER") or ""
DC_CLIENT_ID     = os.environ.get("DISCORD_CLIENT_ID", "")
DC_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DC_REDIRECT_URI  = os.environ.get("DISCORD_REDIRECT_URI",
                                   "https://botshop-01431.onrender.com/auth/discord/callback")
CURRENCY      = "NT$"
SHOP_NAME     = "BotShop"

def _h(prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if prefer: h["Prefer"] = prefer
    return h

def q(table, params):
    r = requests.get(f"{URL}/rest/v1/{table}", headers=_h(), params=params)
    r.raise_for_status(); return r.json()

def ex(method, table, params=None, json=None):
    fn = {"post": requests.post, "patch": requests.patch, "delete": requests.delete}[method]
    kw = {"headers": _h("return=representation")}
    if params: kw["params"] = params
    if json: kw["json"] = json
    r = fn(f"{URL}/rest/v1/{table}", **kw)
    r.raise_for_status(); return r

def current_user():
    return session.get("discord_user")

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not current_user(): return redirect(url_for("index"))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return f(*a, **k)
    return w

@app.route("/")
def index():
    if current_user(): return redirect(url_for("dashboard"))
    return render_template("landing.html", shop=SHOP_NAME)

@app.route("/auth/discord")
def auth_discord():
    if not DC_CLIENT_ID:
        flash("Discord 登入尚未設定")
        return redirect(url_for("index"))
    params = {"client_id": DC_CLIENT_ID, "redirect_uri": DC_REDIRECT_URI,
              "response_type": "code", "scope": "identify"}
    return redirect("https://discord.com/api/oauth2/authorize?" + urlencode(params))

@app.route("/auth/discord/callback")
def auth_discord_callback():
    code = request.args.get("code")
    if not code:
        flash("授權被取消"); return redirect(url_for("index"))
    r = requests.post("https://discord.com/api/oauth2/token", data={
        "client_id": DC_CLIENT_ID, "client_secret": DC_CLIENT_SECRET,
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": DC_REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code != 200:
        flash(f"授權失敗：{r.text[:100]}"); return redirect(url_for("index"))
    token = r.json()["access_token"]
    r = requests.get("https://discord.com/api/users/@me",
                     headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        flash("拿使用者資訊失敗"); return redirect(url_for("index"))
    u = r.json()
    session["discord_user"] = {
        "id": u["id"], "username": u["username"],
        "global_name": u.get("global_name") or u["username"],
        "avatar": u.get("avatar")}
    return redirect(url_for("dashboard"))

@app.route("/auth/logout")
def auth_logout():
    session.pop("discord_user", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    items = q("items", {"select": "id,name,price,stock,description", "order": "id"})
    orders = q("orders", {"user_id": f"eq.{current_user()['id']}",
                          "select": "*,items(name)", "order": "id.desc", "limit": 20})
    for o in orders:
        o["name"] = (o.get("items") or {}).get("name", f"item#{o['item_id']}")
    return render_template("dashboard.html", shop=SHOP_NAME, cur=CURRENCY,
                           user=current_user(), items=items, orders=orders)

@app.route("/dashboard/buy/<int:iid>", methods=["POST"])
@login_required
def dashboard_buy(iid):
    qty = int(request.form.get("qty", 1))
    if qty <= 0:
        flash("數量必須大於 0"); return redirect(url_for("dashboard"))
    items = q("items", {"id": f"eq.{iid}", "select": "id,name,price,stock", "limit": 1})
    if not items:
        flash("找不到商品"); return redirect(url_for("dashboard"))
    it = items[0]
    if it["stock"] < qty:
        flash(f"庫存不足，剩 {it['stock']}"); return redirect(url_for("dashboard"))
    total = it["price"] * qty
    ex("patch", "items", params={"id": f"eq.{iid}"}, json={"stock": it["stock"] - qty})
    ex("post", "orders", json={
        "user_id": int(current_user()["id"]),
        "username": current_user()["global_name"],
        "source": "web", "item_id": iid, "qty": qty, "total": total})
    flash(f"下單成功！{it['name']} × {qty}，共 {CURRENCY}{total}")
    return redirect(url_for("dashboard"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PW:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("密碼錯誤")
    return render_template("login.html", shop=SHOP_NAME)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    try: st = ptero_status()
    except Exception: st = {"state": "unreachable"}
    items = q("items", {"select": "id,name,price,stock,description", "order": "id"})
    orders = q("orders", {"select": "*,items(name)", "order": "id.desc", "limit": 100})
    for o in orders:
        o["name"] = (o.get("items") or {}).get("name", f"item#{o['item_id']}")
    return render_template("admin.html", shop=SHOP_NAME, cur=CURRENCY,
                           st=st, items=items, orders=orders)

@app.route("/admin/item", methods=["POST"])
@admin_required
def admin_item():
    ex("post", "items", params={"on_conflict": "name"},
       json={"name": request.form["name"].strip(),
             "price": int(request.form["price"]),
             "stock": int(request.form["stock"]),
             "description": request.form.get("description","").strip()})
    flash("商品已儲存"); return redirect(url_for("admin"))

@app.route("/admin/item/<int:iid>/delete", methods=["POST"])
@admin_required
def admin_del(iid):
    ex("delete", "items", params={"id": f"eq.{iid}"})
    return redirect(url_for("admin"))

@app.route("/admin/order/<int:oid>/status/<st>", methods=["POST"])
@admin_required
def admin_set(oid, st):
    if st in ("pending","paid","done","cancelled"):
        ex("patch", "orders", params={"id": f"eq.{oid}"}, json={"status": st})
    return redirect(url_for("admin"))

def ptero(sig):
    if not PTERO_URL or not PTERO_KEY: return 500
    return requests.post(f"{PTERO_URL}/api/client/servers/{PTERO_SERVER}/power",
        headers={"Authorization": f"Bearer {PTERO_KEY}",
                 "Content-Type": "application/json", "Accept": "application/json"},
        json={"signal": sig}, timeout=10).status_code

def ptero_status():
    if not PTERO_URL or not PTERO_KEY: return {"state": "not-configured"}
    r = requests.get(f"{PTERO_URL}/api/client/servers/{PTERO_SERVER}/resources",
        headers={"Authorization": f"Bearer {PTERO_KEY}", "Accept": "application/json"},
        timeout=10)
    if r.status_code != 200: return {"state": "unknown"}
    a = r.json().get("attributes", {}); res = a.get("resources", {})
    return {"state": a.get("current_state", "unknown"),
            "cpu": round(res.get("cpu_absolute", 0), 1),
            "ram": res.get("memory_bytes", 0) // 1048576,
            "disk": res.get("disk_bytes", 0) // 1048576,
            "uptime": res.get("uptime", 0) // 1000}

@app.route("/admin/server/<sig>", methods=["POST"])
@admin_required
def admin_srv(sig):
    if sig not in ("start","stop","restart","kill"): return jsonify(ok=False), 400
    try: return jsonify(ok=ptero(sig) < 300)
    except Exception as e: return jsonify(ok=False, msg=str(e)), 500

@app.route("/admin/api/status")
@admin_required
def admin_st():
    try: return jsonify(ptero_status())
    except Exception as e: return jsonify(state="unreachable", error=str(e))



@app.errorhandler(404)
def not_found(e):
    return render_template("404.html", shop=SHOP_NAME), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("404.html", shop=SHOP_NAME), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
