import os, requests
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, render_template, redirect, url_for, session, flash, request
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
