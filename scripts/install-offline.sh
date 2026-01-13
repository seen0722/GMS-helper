#!/bin/bash
set -e

# 檢查是否為 root 或有 docker 權限
if ! docker info > /dev/null 2>&1; then
    echo "錯誤: 無法執行 docker 指令。請確認您有權限或使用 sudo。"
    exit 1
fi

echo "載入 Docker Images..."
docker load < images.tar

echo "設定環境變數..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "已建立 .env 檔案。請編輯 .env 填入您的 API Key。"
    else
        echo "警告: 找不到 .env.example"
    fi
else
    echo ".env 已存在，跳過建立。"
fi

echo "啟動服務..."
docker-compose up -d

echo "部署完成！"
echo "請使用 'docker-compose logs -f' 查看日誌。"
echo "若需測試 Cambrian 連線，請執行："
echo "docker-compose run --rm gms-helper python scripts/test_cambrian.py --token <YOUR_TOKEN>"
