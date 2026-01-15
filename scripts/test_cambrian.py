#!/usr/bin/env python3
"""
Cambrian LLM Gateway 連線測試腳本
用於驗證內網伺服器與 Cambrian 的連線是否正常

使用方式:
    pip install openai httpx
    python test_cambrian.py

或指定參數:
    python test_cambrian.py --url https://api.cambrian.pegatroncorp.com --token YOUR_TOKEN --model "LLAMA 3.3 70B"
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="測試 Cambrian LLM 連線")
    parser.add_argument("--url", default="https://api.cambrian.pegatroncorp.com", help="Cambrian API URL")
    parser.add_argument("--token", required=True, help="API Token")
    parser.add_argument("--model", default="LLAMA 3.3 70B", help="Model name")
    parser.add_argument("--verify-ssl", action="store_true", help="啟用 SSL 驗證 (預設關閉)")
    args = parser.parse_args()

    try:
        import httpx
        from openai import OpenAI
    except ImportError:
        print("❌ 缺少依賴，請執行: pip install openai httpx")
        sys.exit(1)

    verify_ssl = args.verify_ssl
    
    print("=" * 50)
    print("Cambrian LLM Gateway 連線測試")
    print("=" * 50)
    print(f"URL: {args.url}")
    print(f"Model: {args.model}")
    print(f"SSL 驗證: {'開啟' if verify_ssl else '關閉'}")
    print()

    # Test 1: HTTP 連線
    print("[1/3] 測試 HTTP 連線...")
    try:
        headers = {
            "Authorization": f"Bearer {args.token}",
            "Accept": "application/json"
        }
        # 根據用戶驗證更新 endpoint: /assistant/llm_model
        # 處理 url 結尾可能有或沒有 /
        base_url = args.url.rstrip('/')
        url = f"{base_url}/assistant/llm_model"
        
        # 特殊處理: 如果用戶傳入的 url 已經帶有 /v1，嘗試移除它以匹配正確路徑
        if base_url.endswith("/v1"):
             url = base_url.replace("/v1", "/assistant/llm_model")

        print(f"      Target URL: {url}") # 顯示實際打的 URL 方便除錯
        r = httpx.get(url, headers=headers, verify=verify_ssl, timeout=10.0)
        
        if r.status_code == 200:
            print(f"      ✅ HTTP 連線成功")
            data = r.json()
            # 根據文件更新: key 為 "llm_list"
            models = data.get('llm_list', [])
            if models:
                print(f"      可用模型:")
                for m in models[:5]:
                    model_name = m.get('name', 'unknown') # 文件是用 "name"
                    desc = m.get('description', '')
                    print(f"        - {model_name} ({desc})")
                if len(models) > 5:
                    print(f"        ... 還有 {len(models) - 5} 個模型")
            else:
                print("      ⚠️  無法取得模型列表 (llm_list 為空)")
        elif r.status_code == 401:
            print(f"      ❌ 認證失敗 (401) - 請檢查 API Token")
            sys.exit(1)
        else:
            print(f"      ⚠️  HTTP {r.status_code}: {r.text[:100]}")
    except httpx.ConnectError as e:
        print(f"      ❌ 連線失敗: {e}")
        print("      請檢查網路連線和 URL 是否正確")
        sys.exit(1)
    except Exception as e:
        print(f"      ❌ 錯誤: {e}")
        sys.exit(1)

    # Test 2: OpenAI Client 初始化
    print("\n[2/3] 初始化 OpenAI Client...")
    try:
        http_client = httpx.Client(verify=verify_ssl)
        client = OpenAI(
            base_url=args.url,
            api_key=args.token,
            http_client=http_client
        )
        print("      ✅ Client 初始化成功")
    except Exception as e:
        print(f"      ❌ Client 初始化失敗: {e}")
        sys.exit(1)

    # Test 3: LLM 呼叫 (遍歷所有模型)
    print("\n[3/3] 測試 LLM 回應 (遍歷所有模型)...")
    
    # 從 Test 1 收集到的模型列表，如果 Test 1 失敗或沒抓到，就用參數指定的單一模型當作 fallback
    target_models = []
    if 'models' in locals() and models:
        for m in models:
            m_name = m.get('name') # 根據前面 llm_list 結構
            if m_name:
                target_models.append(m_name)
    
    if not target_models:
        print(f"      ⚠️  未偵測到模型列表，使用預設/指定模型: {args.model}")
        target_models = [args.model]

    print(f"      即將測試 {len(target_models)} 個模型: {', '.join(target_models)}")
    
    success_count = 0
    fail_count = 0

    for model_name in target_models:
        print(f"\n      👉 測試模型: {model_name}")
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": "Say 'Hello' in one word only."}
                ],
                max_tokens=10,
                temperature=0
            )
            content = response.choices[0].message.content
            print(f"         ✅ 成功! 回應: {content}")
            success_count += 1
        except Exception as e:
            print(f"         ❌ 失敗: {e}")
            fail_count += 1

    print("\n      " + "-"*30)
    print(f"      測試總結: 成功 {success_count}, 失敗 {fail_count}")
    if success_count == 0:
        sys.exit(1)

    print()
    print("=" * 50)
    print("✅ 所有測試通過！Cambrian 連線正常。")
    print("=" * 50)


if __name__ == "__main__":
    main()
