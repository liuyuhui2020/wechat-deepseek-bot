from flask import Flask, request, abort, Response
from wechatpy import parse_message, create_reply, WeChatClient
from wechatpy.utils import check_signature
from wechatpy.exceptions import InvalidSignatureException
from urllib3.util.retry import Retry 
from requests.adapters import HTTPAdapter  
import requests
import os
import logging
import threading
import time
from datetime import datetime

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 环境变量配置
TOKEN = os.getenv('WECHAT_TOKEN')
APP_ID = os.getenv('WECHAT_APPID')
APP_SECRET = os.getenv('WECHAT_APPSECRET')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# 微信客户端（单例模式）
wechat_client = WeChatClient(APP_ID, APP_SECRET)

# 访问令牌管理
class TokenManager:
    _access_token = None
    _expires_at = 0

    @classmethod
    def get_token(cls):
        if time.time() > cls._expires_at - 300:  # 提前5分钟刷新
            token_info = wechat_client.fetch_access_token()
            cls._access_token = token_info['access_token']
            cls._expires_at = token_info['expires_at']
            logger.info("Refreshed wechat access token")
        return cls._access_token

# 带重试机制的HTTP Session
def create_retry_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 504),
        allowed_methods=frozenset(['POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

deepseek_session = create_retry_session()

def async_deepseek_process(user_id, query):
    """异步处理DeepSeek请求并发送客服消息"""
    try:
        logger.info(f"Start processing for {user_id}")
        
        # 调用DeepSeek API（允许最长60秒）
        start_time = time.time()
        response = deepseek_session.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "messages": [{"role": "user", "content": query}],
                "model": "deepseek-chat",
                "temperature": 0.7
            },
            timeout=(3, 60)  # 允许60秒响应
        )
        response.raise_for_status()
        
        # 处理响应
        reply_content = response.json()['choices'][0]['message']['content']
        cost_time = time.time() - start_time
        logger.info(f"DeepSeek response in {cost_time:.2f}s")

        # 通过客服接口发送
        wechat_client.message.send_text(
            user_id=user_id,
            content=reply_content[:600]  # 微信限制600字符
        )
        
    except Exception as e:
        logger.error(f"Async process failed: {str(e)}")
        # 失败时发送通知消息
        try:
            wechat_client.message.send_text(
                user_id=user_id,
                content="回答生成超时，请稍后重新提问"
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message: {str(inner_e)}")

@app.route('/', methods=['GET', 'POST', 'HEAD'])
def wechat_handler():
    """处理微信验证和消息"""
    # 验证请求
    if request.method == 'GET':
        try:
            check_signature(
                TOKEN,
                request.args.get('signature', ''),
                request.args.get('timestamp', ''),
                request.args.get('nonce', '')
            )
            return request.args.get('echostr', '')
        except InvalidSignatureException:
            abort(403)

    # 处理消息
    if request.method == 'POST':
        # 立即返回空响应（避免超时）
        threading.Thread(target=process_message_async).start()
        return Response(status=200, response='等待智能客服回复~')
        
    elif request.method == "HEAD":
        return '', 200

def process_message_async():
    """异步处理消息"""
    try:
        msg = parse_message(request.data)
        if msg.type != 'text':
            return

        logger.info(f"Received message from {msg.source}: {msg.content}")

        # 启动独立线程处理（避免阻塞）
        processing_thread = threading.Thread(
            target=async_deepseek_process,
            args=(msg.source, msg.content)
        )
        processing_thread.start()

    except Exception as e:
        logger.error(f"Message processing failed: {str(e)}")

if __name__ == '__main__':
    # 预热连接池
    requests.get('https://api.deepseek.com', timeout=2)
    
    # 启动时刷新token
    TokenManager.get_token()
    
    app.run(host='0.0.0.0', port=8000, threaded=True)