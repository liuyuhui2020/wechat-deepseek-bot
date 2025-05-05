import requests
from config import DEEPSEEK_API_KEY

def ask_deepseek(question):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": question}]
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    try:
        return data['choices'][0]['message']['content']
    except Exception as e:
        return "抱歉，AI 接口异常了。"
