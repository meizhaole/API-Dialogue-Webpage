from flask import Flask, render_template, request, jsonify
import websockets
import asyncio
import json
import time
import hmac
import hashlib
import base64
from urllib.parse import urlencode

app = Flask(__name__)

# 配置讯飞星火Spark Max API（替换为你的密钥）
APPID = "4484520c"  # 已开通Spark Max服务的应用ID
APISecret = "ZjhmNjFiMjcyYTc5YjZiZjJmM2MzYjIz"  # 对应应用的APISecret
APIKey = "16552a035fec2943401c72374fb04eec"  # 对应应用的APIKey


# 生成Spark Max的WebSocket连接地址（关键：Max版本专属地址）
def get_url():
    url = "wss://spark-api.xf-yun.com/v3.5/chat"  # Spark Max接口地址
    host = "spark-api.xf-yun.com"
    path = "/v3.5/chat"  # Max版本路径
    now = int(time.time())
    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now))
    # 签名计算（逻辑通用，仅路径适配Max）
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(APISecret.encode('utf-8'), signature_origin.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode(encoding='utf-8')
    authorization_origin = f'api_key="{APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
    v = {
        "authorization": authorization,
        "date": date,
        "host": host
    }
    return f"{url}?{urlencode(v)}"


# 异步调用Spark Max API（无上下文记忆，仅传当前消息）
async def get_spark_reply(user_message):
    url = get_url()
    async with websockets.connect(url) as websocket:
        # 构造请求参数（Max版本专属领域参数）
        data = {
            "header": {
                "app_id": APPID,
                "uid": "user123"  # 任意用户ID
            },
            "parameter": {
                "chat": {
                    "domain": "general",  # Spark Max专属领域参数
                    "temperature": 0.7,  # 随机性（0-1）
                    "max_tokens": 8129  # Max支持更大回复长度（根据需求调整）
                }
            },
            "payload": {
                "message": {
                    "text": [{"role": "user", "content": user_message}]  # 仅当前消息
                }
            }
        }
        await websocket.send(json.dumps(data))

        # 接收并拼接回复
        reply = ""
        while True:
            response = await websocket.recv()
            response_json = json.loads(response)
            if response_json["header"]["status"] == 2:  # 回复结束
                break
            # 提取回复内容（Max返回格式与Pro类似）
            payload = response_json.get("payload", {})
            choices = payload.get("choices", {})
            text_list = choices.get("text", [])
            if text_list and len(text_list) > 0:
                reply += text_list[0].get("content", "")  # 直接取content字段
        return reply


# 首页路由
@app.route('/')
def index():
    return render_template('index.html')


# 对话接口
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"reply": "请输入消息"})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_reply = loop.run_until_complete(get_spark_reply(user_message))
        return jsonify({"reply": bot_reply})
    except Exception as e:
        return jsonify({"reply": f"出错了：{str(e)}"})


if __name__ == '__main__':
    app.run(debug=True)