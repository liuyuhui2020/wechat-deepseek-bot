import hashlib
import xml.etree.ElementTree as ET
from flask import Flask, request, Response
import requests
import os
import time

app = Flask(__name__)

# 从环境变量读取 DeepSeek API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

@app.route("/", methods=["GET", "POST", "HEAD"])
def wechat():
    if request.method == "GET":
        # 微信服务器验证
        token = 'mywechat123token'  # 与微信公众平台设置一致
        query = request.args
        signature = query.get('signature', '')
        timestamp = query.get('timestamp', '')
        nonce = query.get('nonce', '')
        echostr = query.get('echostr', '')

        s = ''.join(sorted([token, timestamp, nonce]))
        if hashlib.sha1(s.encode('utf-8')).hexdigest() == signature:
            print("微信验证成功")
            return echostr
        else:
            print("微信验证失败")
            return "Invalid signature"

    elif request.method == "POST":
        # 接收微信消息并回复
        xml_data = request.data
        print("收到微信消息原始内容：", xml_data)

        try:
            xml = ET.fromstring(xml_data)
            to_user = xml.find('FromUserName').text
            from_user = xml.find('ToUserName').text
            content = xml.find('Content').text.strip()

            print("接收到用户消息：", content)

            reply = call_deepseek(content)
            print("DeepSeek 回复内容：", reply)

            response = f"""
<xml>
  <ToUserName><![CDATA[{to_user}]]></ToUserName>
  <FromUserName><![CDATA[{from_user}]]></FromUserName>
  <CreateTime>{int(time.time())}</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[{reply}]]></Content>
</xml>
"""
            return Response(response, content_type='application/xml')

        except Exception as e:
            print("处理消息出错：", str(e))
            return "error"

    elif request.method == "HEAD":
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
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        resp = session.post(url, headers=headers, json=payload, timeout=180)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("调用 DeepSeek 出错：", str(e))
        return "出错了，请稍后再试～"

if __name__ == "__main__":
    app.run(debug=True)
