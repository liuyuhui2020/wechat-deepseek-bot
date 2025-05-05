from flask import Flask, request, jsonify
import requests
import os  # 新增导入 os 模块

app = Flask(__name__)

# 从环境变量读取 DeepSeek API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")  # 关键修改！

@app.route("/wechat", methods=["POST"])
def wechat_reply():
    if not DEEPSEEK_API_KEY:
        return jsonify({"error": "API Key 未配置"}), 500  # 检查 Key 是否存在

    user_msg = request.json.get("Content", "").strip()
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": user_msg}]}
    )
    return jsonify({"Content": response.json()["choices"][0]["message"]["content"]})

# Netlify Functions 适配器
def handler(event, context):
    from flask_lambda import FlaskLambda
    return FlaskLambda(app)(event, context)