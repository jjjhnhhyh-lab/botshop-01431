import os, requests
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, render_template, redirect, url_for, session, flash, request, jsonify
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_KEY"]

def _h(prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if prefer: h["Prefer"] = prefer
    return h

def q(table, params):
    r = requests.get(f"{URL}/rest/v1/{table}", headers=_h(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def q1(table, params):
    rows = q(table, params)
    return rows[0] if rows else None

def ex(method, table, params=None, json=None):
    fn = {"post": requests.post, "patch": requests.patch, "delete": requests.delete}[method]
    kw = {"headers": _h("return=representation")}
    if params: kw["params"] = params
    if json: kw["json"] = json
    r = fn(f"{URL}/rest/v1/{table}", **kw, timeout=15)
    r.raise_for_status()
    return r

DC_CLIENT_ID     = os.environ.get("DISCORD_CLIENT_ID", "")
DC_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DC_REDIRECT_URI  = os.environ.get("DISCORD_REDIRECT_URI",
                                   "https://botshop-01431.onrender.com/auth/discord/callback")
SHOP_NAME = "BotShop"

def current_user():
    return session.get("discord_user")

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("landing.html", shop=SHOP_NAME)

@app.route("/auth/discord")
def auth_discord():
    if not DC_CLIENT_ID:
        flash("Discord 登入尚未設定")
        return redirect(url_for("index"))
    params = {
        "client_id": DC_CLIENT_ID,
        "redirect_uri": DC_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    return redirect("https://discord.com/api/oauth2/authorize?" + urlencode(params))

@app.route("/auth/discord/callback")
def auth_discord_callback():
    code = request.args.get("code")
    if not code:
        flash("授權被取消")
        return redirect(url_for("index"))
    r = requests.post("https://discord.com/api/oauth2/token", data={
        "client_id": DC_CLIENT_ID, "client_secret": DC_CLIENT_SECRET,
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": DC_REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code != 200:
        flash(f"授權失敗：{r.text[:100]}")
        return redirect(url_for("index"))
    token = r.json()["access_token"]
    r = requests.get("https://discord.com/api/users/@me",
                     headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        flash("拿使用者資訊失敗")
        return redirect(url_for("index"))
    u = r.json()
    session["discord_user"] = {
        "id": u["id"],
        "username": u["username"],
        "global_name": u.get("global_name") or u["username"],
        "avatar": u.get("avatar"),
    }
    return redirect(url_for("dashboard"))

@app.route("/auth/logout")
def auth_logout():
    session.pop("discord_user", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not current_user():
        return redirect(url_for("index"))
    return render_template("dashboard.html", shop=SHOP_NAME, user=current_user())



@app.route("/server/<path:name>")
def server_console(name):
    if not current_user():
        return redirect(url_for("index"))
    return render_template("server_console.html", shop=SHOP_NAME, user=current_user(), server_name=name)



@app.route("/api/server/<action>", methods=["POST"])
def api_server_action(action):
    if not current_user():
        return jsonify(ok=False, msg="not logged in"), 401
    if action not in ("start", "stop", "restart", "kill"):
        return jsonify(ok=False, msg="invalid action"), 400
    
    # 去重：檢查有沒有同 action 的 pending/running job
    check = requests.get(
        f"{URL}/rest/v1/server_jobs",
        headers=_h(),
        params={"action": f"eq.{action}", "status": "in.(pending,running)", "order": "id.desc", "limit": 1},
        timeout=10
    )
    if check.status_code == 200 and check.json():
        existing = check.json()[0]
        return jsonify(ok=True, job_id=existing["id"], cached=True)
    
    r = requests.post(
        f"{URL}/rest/v1/server_jobs",
        headers=_h("return=representation"),
        json={"action": action, "status": "pending"}
    )
    if r.status_code not in (200, 201):
        return jsonify(ok=False, msg="failed to create job"), 500
    job = r.json()[0]
    return jsonify(ok=True, job_id=job["id"])

@app.route("/api/server/status/<int:job_id>")
def api_job_status(job_id):
    if not current_user():
        return jsonify(ok=False), 401
    r = requests.get(
        f"{URL}/rest/v1/server_jobs",
        headers=_h(),
        params={"id": f"eq.{job_id}", "limit": 1}
    )
    if r.status_code != 200 or not r.json():
        return jsonify(ok=False), 404
    return jsonify(ok=True, job=r.json()[0])



@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response



@app.route("/api/files/upload", methods=["POST"])
def api_files_upload():
    if not current_user():
        return jsonify(ok=False, msg="not logged in"), 401
    data = request.get_json()
    if not data:
        return jsonify(ok=False, msg="no data"), 400
    filename = data.get("filename")
    content_b64 = data.get("content")
    if not filename or not content_b64:
        return jsonify(ok=False, msg="missing filename or content"), 400
    import json as _json
    payload = _json.dumps({"filename": filename, "content_b64": content_b64})
    r = requests.post(
        f"{URL}/rest/v1/server_jobs",
        headers=_h("return=representation"),
        json={"action": "write_file", "status": "pending", "payload": payload},
        timeout=15
    )
    if r.status_code not in (200, 201):
        return jsonify(ok=False, msg="failed to create job"), 500
    return jsonify(ok=True, job_id=r.json()[0]["id"])

@app.route("/api/server/command", methods=["POST"])
def api_server_command():
    if not current_user():
        return jsonify(ok=False, msg="not logged in"), 401
    data = request.get_json()
    cmd = (data or {}).get("command", "").strip()
    if not cmd:
        return jsonify(ok=False, msg="empty command"), 400
    import json as _json
    payload = _json.dumps({"command": cmd})
    r = requests.post(
        f"{URL}/rest/v1/server_jobs",
        headers=_h("return=representation"),
        json={"action": "send_command", "status": "pending", "payload": payload},
        timeout=15
    )
    if r.status_code not in (200, 201):
        return jsonify(ok=False, msg="failed to create job"), 500
    return jsonify(ok=True, job_id=r.json()[0]["id"])



@app.route("/api/console/recent")
def api_console_recent():
    if not current_user():
        return jsonify(ok=False), 401
    since_id = request.args.get("since_id", 0, type=int)
    r = requests.get(
        f"{URL}/rest/v1/console_logs",
        headers=_h(),
        params={"id": f"gt.{since_id}", "order": "id.asc", "limit": 100},
        timeout=10
    )
    if r.status_code != 200:
        return jsonify(ok=False), 500
    return jsonify(ok=True, lines=r.json())



@app.route("/api/code/list")
def api_code_list():
    if not current_user():
        return jsonify(ok=False), 401
    r = requests.get(
        f"{URL}/rest/v1/user_code",
        headers=_h(),
        params={"select": "filename,updated_at", "order": "filename"},
        timeout=10
    )
    return jsonify(ok=True, files=r.json())

@app.route("/api/code/read")
def api_code_read():
    if not current_user():
        return jsonify(ok=False), 401
    fname = request.args.get("file", "")
    if not fname:
        return jsonify(ok=False, msg="missing file"), 400
    r = requests.get(
        f"{URL}/rest/v1/user_code",
        headers=_h(),
        params={"filename": f"eq.{fname}", "limit": 1},
        timeout=10
    )
    if r.status_code != 200 or not r.json():
        return jsonify(ok=False, msg="not found"), 404
    return jsonify(ok=True, content=r.json()[0]["content"])

@app.route("/api/code/save", methods=["POST"])
def api_code_save():
    if not current_user():
        return jsonify(ok=False), 401
    data = request.get_json()
    if not data:
        return jsonify(ok=False), 400
    fname = (data.get("filename") or "").strip()
    content = data.get("content", "")
    if not fname:
        return jsonify(ok=False, msg="missing filename"), 400

    # 1. Upsert to Supabase
    r = requests.post(
        f"{URL}/rest/v1/user_code",
        headers=_h(),
        params={"on_conflict": "filename"},
        json={"filename": fname, "content": content},
        timeout=10
    )

    # 2. Trigger write_file job (so bot pushes to Pterodactyl)
    import json as _json, base64 as _b64
    payload = _json.dumps({"filename": fname, "content_b64": _b64.b64encode(content.encode()).decode()})
    r2 = requests.post(
        f"{URL}/rest/v1/server_jobs",
        headers=_h("return=representation"),
        json={"action": "write_file", "status": "pending", "payload": payload},
        timeout=10
    )
    return jsonify(ok=True, job_id=r2.json()[0]["id"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
