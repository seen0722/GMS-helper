#!/bin/bash

# 預設值
URL="https://api.cambrian.pegatroncorp.com"
TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTM0NjIzOTksInVzZXJuYW1lIjoiYmlsbHlfY2hlbiIsImlhdCI6MTc2ODM4MDQ5MSwianRpIjoiM2MzYzM0N2UtOTQ0My00Yjk2LWE1NzUtYzM5YzkyMzZjZDkzIiwiZ3JvdXAiOiJDQU1CUklBTiIsInVzZXJfaWQiOiI4OGQ1OGM2Mi1hZmI2LTQxMzYtYjliZS05YTdjNjliYzU2Y2MiLCJzY3AiOnt9LCJyb2xlIjoidXNlciIsImlwIjoicG9ydGFsIiwidG9rZW5fdHlwZSI6ImV4dGVybmFsIiwidG9rZW5fbmFtZSI6ImRlZmF1bHQifQ.IBZWCxS_LROVpuyFFDmVUWtcskVGPsJ0dO_3BLBaNm_4xInxI3ruXHVjxbrrB-ASWTmTudaO_eEEl8DPSQ7-qFTGxRXSutta8IQmyT7w4Mag1y__s2op0ZhbP32VP7eIg-n83LQYaH0-PZBff9zffJ4FdBoQOC_ql5OQOqYUV346WOahb_C3xK1Q58imV8VP_6-WBDHBA2GwenEpm8vk1wrLLSSrDg9XggvCtkHVYDBZVDgYKa2n0MiYzP_JO0z2RlX9jHkv4Vy-okJYxA9KMPzvYKYxSHl_XjiUDMWM6xeKxShBVyCtvqMZTo1oMXMNe67oIqLqi0ukWnGB-eIJg7ZdoXPlGSPN6bxBU5tRC8d9YwVrpjMo_aYUpWzevCcoiF0P1ESjKO4pZz0CRYPSjC1jAVfHS1JmH61gppBo-mEelCqsvbxVOvcOXoRGcGsTc2NkgpzqJSfyaczKPyx8JcU7l1WeMTr6v_LdEIV9XH1X5uHtrQXzo0whgtkpQNcD_sfa83L_QUh4i69CvhlguPknPkLchn7or1_CL8zotf-uIaqwsiIHPVMS4R9KfJM53xf4IcOjq8fAm38XJzlPO2wWkkH2wASTq8EudRVmS5Rb9mZFc2I2KXv8I8Cp94H80-Wto5SjFLcuk83BcWzkJgZCnp4BF3QQq4Q_7RLrT04"
MODEL="LLAMA 3.3 70B"

# 解析參數
usage() {
    echo "Usage: $0 --token <API_TOKEN> [--url <URL>] [--model <MODEL_NAME>]"
    echo "Example:"
    echo "  $0 --token my-secret-token"
    exit 1
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --token) TOKEN="$2"; shift ;;
        --url) URL="$2"; shift ;;
        --model) MODEL="$2"; shift ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

if [ -z "$TOKEN" ]; then
    echo "Error: Token is required."
    usage
fi

# 移除 URL 尾部斜線
URL=${URL%/}

echo "================================================"
echo "          Cambrian Curl Test Script             "
echo "================================================"
echo "URL: $TOKEN (hidden)"
echo "URL: $URL"
echo "Model: $MODEL"
echo "================================================"

# 1. 測試模型列表
echo ""
echo "[1/2] Testing Model List (/assistant/llm_model)..."
LIST_URL="${URL}/assistant/llm_model"

# 如果 base URL 有 /v1，嘗試替換
if [[ "$URL" == *"/v1" ]]; then
    LIST_URL="${URL/\/v1/\/assistant\/llm_model}"
fi

echo "Connecting to: $LIST_URL"
RESPONSE=$(curl -k -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$LIST_URL" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer $TOKEN")

HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS:.*//')

if [ "$HTTP_STATUS" == "200" ]; then
    echo "✅ Success (HTTP 200)"
    echo "Raw Response (First 200 chars): ${BODY:0:200}..."
    
    # 嘗試用 grep 抓出模型名稱 (簡單解析)
    echo "Detected Models:"
    echo "$BODY" | grep -o '"name": *"[^"]*"' | cut -d'"' -f4 | head -n 5
    echo "..."
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
    # 不強制退出，繼續測 Chat
fi

# 2. 測試 Chat Completion
echo ""
echo "[2/2] Testing Chat Completion (/v1/chat/completions)..."
CHAT_URL="${URL}/v1/chat/completions"

# 準備 JSON Payload
JSON_DATA=$(cat <<EOF
{
  "model": "$MODEL",
  "messages": [{"role": "user", "content": "Say Hello"}],
  "max_tokens": 10,
  "temperature": 0
}
EOF
)

echo "Connecting to: $CHAT_URL"
echo "Payload: $JSON_DATA"

RESPONSE=$(curl -k -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$CHAT_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$JSON_DATA")

HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS:.*//')

if [ "$HTTP_STATUS" == "200" ]; then
    echo "✅ Success (HTTP 200)"
    echo "Raw Response: $BODY"
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

echo ""
echo "Done."
