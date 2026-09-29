import os, requests
from pathlib import Path
from functools import wraps
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
CURRENCY      = "NT$"
SHOP_NAME     = "BotShop"

def _h(prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
         "Content-Type": "application/json"}
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

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a, **k)
    return w

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PW:
            session["admin"] = True; return redirect(url_for("admin"))
        flash("密碼錯誤")
    return render_template("login.html", shop=SHOP_NAME)

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/")
def index():
    items = q("items", {"select": "id,name,price,stock,description", "order": "id"})
    return render_template("index.html", shop=SHOP_NAME, cur=CURRENCY, items=items)

@app.route("/buy/<int:iid>", methods=["POST"])
def buy(iid):
    qty = int(request.form.get("qty", 1))
    name = (request.form.get("username") or "訪客").strip()[:32] or "訪客"
    if qty <= 0: flash("數量必須大於 0"); return redirect(url_for("index"))
    items = q("items", {"id": f"eq.{iid}", "select": "id,name,price,stock", "limit": 1})
    if not items: flash("找不到商品"); return redirect(url_for("index"))
    it = items[0]
    if it["stock"] < qty: flash(f"庫存不足，剩 {it['stock']}"); return redirect(url_for("index"))
    total = it["price"] * qty
    ex("patch", "items", params={"id": f"eq.{iid}"}, json={"stock": it["stock"] - qty})
    ex("post", "orders", json={"user_id": 0, "username": name, "source": "web",
                                "item_id": iid, "qty": qty, "total": total})
    flash(f"下單成功！{it['name']} × {qty}，共 {CURRENCY}{total}")
    return redirect(url_for("index"))

@app.route("/my-orders")
def my_orders():
    name = (request.args.get("username") or "").strip(); rows = []
    if name:
        rows = q("orders", {"username": f"eq.{name}", "select": "*,items(name)",
                            "order": "id.desc", "limit": 50})
        for o in rows:
            o["name"] = (o.get("items") or {}).get("name", f"item#{o['item_id']}")
    return render_template("my_orders.html", shop=SHOP_NAME, cur=CURRENCY, rows=rows, name=name)

@app.route("/admin")
@login_required
def admin():
    try: st = ptero_status()
    except Exception: st = {"state": "unreachable"}
    items = q("items", {"select": "id,name,price,stock,description", "order": "id"})
    orders = q("orders", {"select": "*,items(name)", "order": "id.desc", "limit": 100})
    for o in orders:
        o["name"] = (o.get("items") or {}).get("name", f"item#{o['item_id']}")
    return render_template("admin.html", shop=SHOP_NAME, cur=CURRENCY, st=st,
                           items=items, orders=orders)

@app.route("/admin/item", methods=["POST"])
@login_required
def admin_item():
    ex("post", "items", params={"on_conflict": "name"},
       json={"name": request.form["name"].strip(),
             "price": int(request.form["price"]),
             "stock": int(request.form["stock"]),
             "description": request.form.get("description","").strip()})
    flash("商品已儲存"); return redirect(url_for("admin"))

@app.route("/admin/item/<int:iid>/delete", methods=["POST"])
@login_required
def admin_del(iid):
    ex("delete", "items", params={"id": f"eq.{iid}"})
    return redirect(url_for("admin"))

@app.route("/admin/order/<int:oid>/status/<st>", methods=["POST"])
@login_required
def admin_set(oid, st):
    if st in ("pending","paid","done","cancelled"):
        ex("patch", "orders", params={"id": f"eq.{oid}"}, json={"status": st})
    return redirect(url_for("admin"))

@app.route("/admin/server/<sig>", methods=["POST"])
@login_required
def admin_srv(sig):
    if sig not in ("start","stop","restart","kill"): return jsonify(ok=False), 400
    try: return jsonify(ok=ptero(sig) < 300)
    except Exception as e: return jsonify(ok=False, msg=str(e)), 500

@app.route("/admin/api/status")
@login_required
def admin_st():
    try: return jsonify(ptero_status())
    except Exception as e: return jsonify(state="unreachable", error=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
