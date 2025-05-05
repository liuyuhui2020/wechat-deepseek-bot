import hashlib
import xml.etree.ElementTree as ET
from flask import Flask, request, Response, make_response
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import time
import threading
import logging
from wechatpy import WeChatClient
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException

app = Flask(__name__)

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量读取配置
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "mywechat123token")
WECHAT_APPID = os.environ.get("WECHAT_APPID")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET")
ENCODING_AES_KEY = os.environ.get("ENCODING_AES_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 初始化微信客户端
crypto = WeChatCrypto(WECHAT_TOKEN, ENCODING_AES_KEY, WECHAT_APPID)
wx_client = WeChatClient(WECHAT_APPID, WECHAT_SECRET)

def build_xml_response(to_user, from_user, content):
    """构建符合微信要求的XML响应"""
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
    """异步处理消息并发送客服消息"""
    try:
        logger.info(f"开始处理异步请求，用户：{to_user}")
        
        # 调用DeepSeek API
        reply = call_deepseek(content)
        logger.info(f"DeepSeek回复内容：{reply[:50]}...")  # 截取部分内容避免日志过大
        
        # 发送客服消息
        wx_client.message.send_text(to_user, reply)
        logger.info("客服消息发送成功")
    except Exception as e:
        logger.error(f"异步处理失败：{str(e)}")
        try:
            wx_client.message.send_text(to_user, "服务暂时不可用，请稍后重试")
        except Exception as inner_e:
            logger.error(f"发送错误消息失败：{str(inner_e)}")

def call_deepseek(user_input):
    """调用DeepSeek API（带超时控制）"""
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
        
        # 设置合理超时（连接3秒，读取15秒）
        resp = session.post(url, headers=headers, json=payload, timeout=(3, 15))
        resp.raise_for_status()
        
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        logger.warning("DeepSeek API请求超时")
        return "请求超时，请稍后重试"
    except KeyError:
        logger.error("API响应格式异常")
        return "服务响应异常，请稍后再试"
    except Exception as e:
        logger.error(f"API调用失败：{str(e)}")
        return "服务暂时不可用，请稍后再试"

@app.route("/", methods=["GET", "POST", "HEAD"])
def wechat():
    if request.method == "GET":
        # 微信服务器验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')

        s = ''.join(sorted([WECHAT_TOKEN, timestamp, nonce]))
        if hashlib.sha1(s.encode()).hexdigest() == signature:
            logger.info("微信验证成功")
            return echostr
        logger.warning("微信验证失败")
        return "Invalid signature"

    elif request.method == "POST":
        try:
            # 测试号使用明文模式，无需解密
            if ENCODING_AES_KEY:  # 正式环境
                encrypted_xml = request.data
                timestamp = request.args.get('timestamp')
                nonce = request.args.get('nonce')
                msg_signature = request.args.get('msg_signature')
                decrypted_xml = crypto.decrypt_message(encrypted_xml, msg_signature, timestamp, nonce)
                xml = ET.fromstring(decrypted_xml)
            else:  # 测试号环境
                xml = ET.fromstring(request.data)  # 直接解析明文XML
            
            # 解析消息
            to_user = xml.find('FromUserName').text
            from_user = xml.find('ToUserName').text
            content = xml.find('Content').text.strip() if xml.find('Content') is not None else ""
            
            logger.info(f"收到消息 - 用户：{to_user}，内容：{content[:50]}...")

            # 立即返回空响应
            response = build_xml_response(to_user, from_user, "")
            
            # 启动异步处理
            threading.Thread(
                target=async_reply,
                args=(to_user, content),
                daemon=True
            ).start()
            
            return response

        except InvalidSignatureException:
            logger.error("签名验证失败")
            return "Invalid signature", 403
        except Exception as e:
            logger.error(f"消息处理异常：{str(e)}")
            return build_xml_response("", "", "系统错误"), 500

    elif request.method == "HEAD":
        return '', 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)