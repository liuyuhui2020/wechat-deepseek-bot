# app.py
import hashlib
import xml.etree.ElementTree as ET
from flask import Flask, request, make_response
import requests
import os

app = Flask(__name__)

# 从环境变量中读取
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")


@app.route("/", methods=["GET", "POST", "HEAD"])
def wechat():
    if request.method == "GET":
        # 验证服务器（微信公众号配置服务器地址时使用）
        token = 'mywechat123token'  # 与微信公众平台设置保持一致
        query = request.args
        signature = query.get('signature', '')
        timestamp = query.get('timestamp', '')
        nonce = query.get('nonce', '')
        echostr = query.get('echostr', '')

        s = ''.join(sorted([token, timestamp, nonce]))
        
        if hashlib.sha1(s.encode('utf-8')).hexdigest() == signature:
            return echostr
        else:
            return "Invalid signature"
    
    elif request.method == "POST":
        # 接收微信用户消息并响应
        xml_data = request.data
        xml = ET.fromstring(xml_data)
        to_user = xml.find('FromUserName').text
        from_user = xml.find('ToUserName').text
        content = xml.find('Content').text

        # 调用 DeepSeek 接口
        reply = call_deepseek(content)

        response = f"""
        <xml>
          <ToUserName><![CDATA[{to_user}]]></ToUserName>
          <FromUserName><![CDATA[{from_user}]]></FromUserName>
          <CreateTime>{int(time.time())}</CreateTime>
          <MsgType><![CDATA[text]]></MsgType>
          <Content><![CDATA[{reply}]]></Content>
        </xml>
        """
        return make_response(response)
    
    elif request.method == "HEAD":
        # Render 或微信可能会发送 HEAD 请求探测服务
        return '', 200

def call_deepseek(user_input):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": user_input}
        ]
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return "出错了，请稍后再试～"

import time
if __name__ == "__main__":
    app.run(debug=True)
