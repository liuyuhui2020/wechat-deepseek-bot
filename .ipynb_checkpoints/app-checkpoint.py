from flask import Flask, request, abort
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import InvalidSignatureException
import requests
import os
import logging

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置从环境变量获取
TOKEN = os.getenv('WECHAT_TOKEN')
APP_ID = os.getenv('WECHAT_APPID')
APP_SECRET = os.getenv('WECHAT_APPSECRET')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

@app.route('/', methods=['GET', 'POST', 'HEAD'])
def wechat():
    """核心处理逻辑"""
    # 记录请求基本信息
    logger.info(f"Incoming {request.method} request from {request.remote_addr}")
    
    # HEAD请求处理（Render健康检查）
    if request.method == 'HEAD':
        logger.info("HEAD request processed for health check")
        return '', 200

    # GET请求处理（微信验证）
    elif request.method == 'GET':
        try:
            signature = request.args.get('signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            logger.debug(f"Validation params: signature={signature}, timestamp={timestamp}, nonce={nonce}")
            
            check_signature(TOKEN, signature, timestamp, nonce)
            logger.info("Signature validation passed")
            return request.args.get('echostr', '')
        except InvalidSignatureException as e:
            logger.error(f"Signature validation failed: {str(e)}")
            abort(403)

    # POST请求处理（消息事件）
    elif request.method == 'POST':
        try:
            # 解析消息
            msg = parse_message(request.data)
            logger.info(f"Received {msg.type} message: {msg.content}")
            
            # 只处理文本消息
            if msg.type == 'text':
                logger.debug(f"Calling DeepSeek API with query: {msg.content}")
                
                # 调用大模型接口
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "messages": [{"role": "user", "content": msg.content}],
                        "model": "deepseek-chat",
                        "temperature": 0.7
                    },
                    timeout=10
                )
                logger.info(f"DeepSeek API response status: {response.status_code}")

                if response.status_code == 200:
                    reply_content = response.json()['choices'][0]['message']['content']
                    logger.debug(f"API response content: {reply_content}")
                else:
                    reply_content = "服务暂时不可用，请稍后再试"
                    logger.error(f"API error: {response.text}")

                # 构造回复
                reply = create_reply(reply_content, msg)
                logger.info(f"Generated reply: {reply_content}")
                return reply.render()
            
            return ''
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            abort(500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)