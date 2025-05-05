# app.py

from flask import Flask, request, make_response
import hashlib
import xml.etree.ElementTree as ET
from deepseek import ask_deepseek
from config import TOKEN

app = Flask(__name__)

@app.route('/wechat', methods=['GET', 'POST'])
def wechat():
    if request.method == 'GET':
        # 微信公众号接口验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')

        tmp = [TOKEN, timestamp, nonce]
        tmp.sort()
        tmp_str = ''.join(tmp)
        hashcode = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()

        if hashcode == signature:
            return echostr
        else:
            return "验证失败"
    
    elif request.method == 'POST':
        # 接收消息并自动回复
        xml_data = request.data
        xml = ET.fromstring(xml_data)
        to_user = xml.find('ToUserName').text
        from_user = xml.find('FromUserName').text
        content = xml.find('Content').text if xml.find('Content') is not None else "你好"

        reply = ask_deepseek(content)

        response = f"""
        <xml>
          <ToUserName><![CDATA[{from_user}]]></ToUserName>
          <FromUserName><![CDATA[{to_user}]]></FromUserName>
          <CreateTime>{int(time.time())}</CreateTime>
          <MsgType><![CDATA[text]]></MsgType>
          <Content><![CDATA[{reply}]]></Content>
        </xml>
        """

        return make_response(response)

if __name__ == '__main__':
    import time
    app.run(host='0.0.0.0', port=8000)
