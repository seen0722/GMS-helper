#!/bin/bash
set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PACKAGE_DIR="gms-helper-offline-${TIMESTAMP}"
OUTPUT_FILE="${PACKAGE_DIR}.tar.gz"

echo "開始打包由 gms-helper-offline..."
echo "建立打包目錄: ${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}"

# 1. Build Docker Images
echo "建構 Docker Image..."
# 確保我們有最新的 base images (但在離線打包機上可能不一定需要 pull，這假設打包機有網)
# docker-compose pull 
docker-compose build

# 2. Save Docker Images
echo "匯出 Docker Images to ${PACKAGE_DIR}/images.tar ..."
# 這裡假設 docker-compose.yml 裡面的 image name 是 gms-helper:latest
# 讀取 docker-compose.yml 確認 image name (這裡 hardcode 為 gms-helper:latest，需與 docker-compose.yml 一致)
docker save -o "${PACKAGE_DIR}/images.tar" gms-helper:latest

# 3. 複製必要檔案
echo "複製設定檔與腳本..."
cp docker-compose.yml "${PACKAGE_DIR}/"
cp .env.example "${PACKAGE_DIR}/" 2>/dev/null || touch "${PACKAGE_DIR}/.env.example"
cp -r scripts "${PACKAGE_DIR}/"
cp -r migrations "${PACKAGE_DIR}/" 2>/dev/null || true # 如果有 migrations

# 複製安裝腳本
cp scripts/install-offline.sh "${PACKAGE_DIR}/install.sh"
chmod +x "${PACKAGE_DIR}/install.sh"

# 4. 打包壓縮
echo "壓縮成 tar.gz..."
tar -czvf "${OUTPUT_FILE}" "${PACKAGE_DIR}"

# 清理暫存檔
rm -rf "${PACKAGE_DIR}"

echo "打包完成: ${OUTPUT_FILE}"
echo "你可以使用 SCP 將此檔案傳輸到內網伺服器。"
