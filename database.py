import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_KEY"]

def _h(prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
         "Content-Type": "application/json"}
    if prefer: h["Prefer"] = prefer
    return h

def init(): pass

def add_item(name, price, stock, desc=""):
    r = requests.post(f"{URL}/rest/v1/items", headers=_h(),
        params={"on_conflict": "name"},
        json={"name": name, "price": price, "stock": stock, "description": desc})
    r.raise_for_status()

def remove_item(name):
    r = requests.delete(f"{URL}/rest/v1/items", headers=_h(),
        params={"name": f"eq.{name}"})
    r.raise_for_status()
    return True

def list_items():
    r = requests.get(f"{URL}/rest/v1/items", headers=_h(),
        params={"select": "id,name,price,stock,description", "order": "id"})
    r.raise_for_status()
    return [(x["id"], x["name"], x["price"], x["stock"], x["description"]) for x in r.json()]

def get_item(name):
    r = requests.get(f"{URL}/rest/v1/items", headers=_h(),
        params={"name": f"eq.{name}", "select": "id,name,price,stock", "limit": 1})
    r.raise_for_status()
    rows = r.json()
    if not rows: return None
    x = rows[0]
    return (x["id"], x["name"], x["price"], x["stock"])

def create_order(user_id, item_id, qty, total, username=None, source="discord"):
    r = requests.post(f"{URL}/rest/v1/orders", headers=_h("return=representation"),
        json={"user_id": user_id, "username": username, "source": source,
              "item_id": item_id, "qty": qty, "total": total})
    r.raise_for_status()
    return r.json()[0]["id"]

def user_orders(user_id):
    r = requests.get(f"{URL}/rest/v1/orders", headers=_h(),
        params={"user_id": f"eq.{user_id}", "select": "*,items(name)", "order": "id.desc"})
    r.raise_for_status()
    return [(x["id"], (x.get("items") or {}).get("name", f"item#{x['item_id']}"),
             x["qty"], x["total"], x["status"], x["created_at"]) for x in r.json()]

def all_orders():
    r = requests.get(f"{URL}/rest/v1/orders", headers=_h(),
        params={"select": "*,items(name)", "order": "id.desc"})
    r.raise_for_status()
    return [(x["id"], x["user_id"], (x.get("items") or {}).get("name", f"item#{x['item_id']}"),
             x["qty"], x["total"], x["status"], x["created_at"]) for x in r.json()]

def set_status(order_id, status):
    r = requests.patch(f"{URL}/rest/v1/orders", headers=_h(),
        params={"id": f"eq.{order_id}"}, json={"status": status})
    r.raise_for_status()
    return True
