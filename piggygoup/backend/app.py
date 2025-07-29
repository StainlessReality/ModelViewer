import os
import time
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request, jsonify, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")

CLIENT_ID = os.environ.get("TRUELAYER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("TRUELAYER_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("TRUELAYER_REDIRECT_URI", "http://localhost:5000/callback")
TRUELAYER_URL = os.environ.get("TRUELAYER_URL", "https://auth.truelayer-sandbox.com")
TOKEN_FILE = "token.json"
SCOPES = "info accounts balance"


def save_token(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def refresh_token(token_data):
    if not token_data:
        return None
    if token_data.get("expires_at", 0) > time.time() + 60:
        return token_data
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    resp = requests.post(f"{TRUELAYER_URL}/connect/token", data=data)
    if resp.status_code == 200:
        new_data = resp.json()
        new_data["refresh_token"] = new_data.get("refresh_token", token_data["refresh_token"])
        new_data["expires_at"] = time.time() + new_data["expires_in"]
        save_token(new_data)
        return new_data
    return None


@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


@app.route("/login")
def login():
    qs = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "providers": "uk-ob-all",
    })
    return redirect(f"{TRUELAYER_URL}/?{qs}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    resp = requests.post(f"{TRUELAYER_URL}/connect/token", data=data)
    if resp.status_code != 200:
        return f"Error fetching token: {resp.text}", 400
    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data["expires_in"]
    save_token(token_data)
    return redirect("/")


@app.route("/api/balance")
def api_balance():
    token_data = refresh_token(load_token())
    if not token_data:
        return jsonify({"error": "Not authenticated"}), 401
    headers = {"Authorization": f"Bearer {token_data['access_token']}", "Accept": "application/json"}
    resp = requests.get("https://api.truelayer-sandbox.com/data/v1/accounts", headers=headers)
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch accounts"}), 400
    accounts = resp.json().get("results", [])
    if not accounts:
        return jsonify({"error": "No accounts found"}), 404
    account_id = accounts[0]["account_id"]
    bal_resp = requests.get(f"https://api.truelayer-sandbox.com/data/v1/accounts/{account_id}/balance", headers=headers)
    if bal_resp.status_code != 200:
        return jsonify({"error": "Failed to fetch balance"}), 400
    bal = bal_resp.json().get("results", [{}])[0]
    amount = bal.get("current", 0)
    ts = datetime.utcnow().isoformat()
    return jsonify({"P": amount, "ts": ts})


if __name__ == "__main__":
    app.run(debug=True)
