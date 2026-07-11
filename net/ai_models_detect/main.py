import requests
import json
from datetime import datetime

BASE_URL = "http://192.168.12.76:62422/v1"

KNOWN_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "glm-4.5",
    "glm-4.5-air",
    "glm-4.6",
    "glm-4.7",
    "glm-5",
    "glm-5-turbo",
    "glm-5.1",
    "kimi-for-coding",
    "MiniMax-M2",
    "MiniMax-M2.1",
    "MiniMax-M2.1-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.5-highspeed",
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M3",
    "glm-5.2",
]

def test_connection():
    print(f"[{datetime.now()}] 正在连接到 {BASE_URL} ...\n")
    
    try:
        response = requests.post(
            BASE_URL + "/chat/completions",
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[OK] 连接成功 (状态码: {response.status_code})")
            print(f"     模型 'deepseek-v4-flash' 可用\n")
            return True
        else:
            print(f"[WARN] 连接响应: 状态码 {response.status_code}")
            print(f"       响应: {response.text[:200]}\n")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] 连接失败: 无法连接到 {BASE_URL}")
        print("       请检查服务是否运行或网络是否通畅。\n")
        return False
    except requests.exceptions.Timeout:
        print(f"[FAIL] 超时: 连接超时\n")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] 请求错误: {e}\n")
        return False

def fetch_models():
    connected = test_connection()
    
    print("-" * 50)
    print(f"[*] 已知的模型列表 (共 {len(KNOWN_MODELS)} 个):\n")
    
    for i, model in enumerate(KNOWN_MODELS, 1):
        print(f"  {i}. {model}")
    
    print("\n" + "=" * 50)
    print("NOTE: 此服务器 (sub2api) 不实现模型发现端点 (/v1/models)")
    print("      模型列表来自配置文件，不是动态获取的。")

if __name__ == "__main__":
    fetch_models()