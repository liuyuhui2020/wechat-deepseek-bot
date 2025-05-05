import hashlib
import xml.etree.ElementTree as ET
from flask import Flask, request, make_response
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import time
import threading
import logging

# 微信相关库动态导入（兼容测试号）
try:
    from wechatpy import WeChatClient
    from wechatpy.crypto import WeChatCrypto
    from wechatpy.exceptions import InvalidSignatureException
except ImportError:
    pass

app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量读取配置
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "your_default_token")
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")
ENCODING_AES_KEY = os.environ.get("ENCODING_AES_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 初始化微信客户端（兼容测试号）
wx_client = None
crypto = None
if WECHAT_APPID and WECHAT_SECRET:
    try:
        wx_client = WeChatClient(WECHAT_APPID, WECHAT_SECRET)
        if ENCODING_AES_KEY:
            crypto = WeChatCrypto(WECHAT_TOKEN, ENCODING_AES_KEY, WECHAT_APPID)
    except NameError:
        logger.warning("微信SDK未正确安装，消息加解密功能不可用")

def build_xml_response(to_user, from_user, content):
    """构建微信XML响应"""
    xml = ET.Element('xml')
    ET.SubElement(xml, 'ToUserName').text = f'<![CDATA[{to_user}]]>'
    ET.SubElement(xml, 'FromUserName').text = f'<![CDATA[{from_user}]]>'
    ET.SubElement(xml, 'CreateTime').text = str(int(time.time()))
    ET.SubElement(xml, 'MsgType').text = '<![CDATA[text]]>'
    content_elem = ET.SubElement(xml, 'Content')
    content_elem.text = f'<![CDATA[{content}]]>' if content else ''
    
    response = make_response(ET.tostring(xml, encoding='utf-8'))
    response.content_type = 'application/xml'
    return response

def async_reply(to_user, content):
    """异步处理消息"""
    try:
        logger.info(f"处理用户消息：{to_user}")
        reply = call_deepseek(content)
        logger.info(f"生成回复：{reply[:50]}...")
        
        if wx_client:
            wx_client.message.send_text(to_user, reply)
        else:
            logger.warning("未配置微信客户端，无法发送客服消息")
    except Exception as e:
        logger.error(f"异步处理失败：{str(e)}")

def call_deepseek(user_input):
    """调用DeepSeek API"""
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": user_input}]
    }
    
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        resp = session.post(url, headers=headers, json=payload, timeout=(3, 15))
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "请求超时，请稍后重试"
    except Exception as e:
        logger.error(f"API调用失败：{str(e)}")
        return "服务暂时不可用"

@app.route("/", methods=["GET", "POST", "HEAD"])
def wechat():
    if request.method == "GET":
        # 微信验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')

        s = ''.join(sorted([WECHAT_TOKEN, timestamp, nonce]))
        if hashlib.sha1(s.encode()).hexdigest() == signature:
            return echostr
        return "验证失败"

    elif request.method == "POST":
        try:
            # 消息处理
            raw_data = request.data
            xml = None
            
            if crypto:
                # 正式环境解密
                timestamp = request.args.get('timestamp')
                nonce = request.args.get('nonce')
                msg_signature = request.args.get('msg_signature')
                decrypted_xml = crypto.decrypt_message(
                    raw_data,
                    msg_signature,
                    timestamp,
                    nonce
                )
                xml = ET.fromstring(decrypted_xml)
            else:
                # 测试号明文处理
                xml = ET.fromstring(raw_data)

            to_user = xml.find('FromUserName').text
            from_user = xml.find('ToUserName').text
            content = xml.find('Content').text.strip() if xml.find('Content') else ""

            # 启动异步处理
            threading.Thread(target=async_reply, args=(to_user, content)).start()
            
            # 立即返回空响应
            return build_xml_response(to_user, from_user, "")

        except Exception as e:
            logger.error(f"处理异常：{str(e)}")
            return build_xml_response("", "", "系统错误"), 500

    elif request.method == "HEAD":
        return '', 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)