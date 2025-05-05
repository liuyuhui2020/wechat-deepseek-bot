from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

DEEPSEEK_API_KEY = "sk-2dedb7a6c48b47ca8d9f71074c31dc4e"  # 替换成你的 DeepSeek API Key

@app.route("/wechat", methods=["POST"])
def wechat_reply():
    user_msg = request.json.get("Content", "").strip()
    
    # 调用 DeepSeek API
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": user_msg}]
        }
    )
    
    reply = response.json()["choices"][0]["message"]["content"]
    return jsonify({"ToUserName": request.json.get("FromUserName"), "Content": reply})

if __name__ == "__main__":
    app.run()