from flask import Flask, request, jsonify
import requests
import os
import awsgi  

app = Flask(__name__)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

@app.route("/wechat", methods=["POST"])
def wechat_reply():
    user_msg = request.json.get("Content", "").strip()
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": user_msg}]}
    )
    return jsonify({"Content": response.json()["choices"][0]["message"]["content"]})

def handler(event, context):
    return awsgi.response(app, event, context) 