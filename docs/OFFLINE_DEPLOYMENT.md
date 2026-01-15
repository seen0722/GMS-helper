# 離線部署指南 (Air-Gapped Deployment)

本文件說明如何在無外部網路的內網伺服器上部署 GMS-Helper。

## 環境需求

| 項目 | 版本 |
|------|------|
| OS | Ubuntu 20.04+ |
| Docker | 20.10+ |
| Docker Compose | v2.x |

---

## 快速開始

### 1. 開發機打包 (有網路)

```bash
cd /path/to/GMS-helper
./scripts/package-offline.sh
```

輸出：`gms-helper-offline-YYYYMMDD-HHMMSS.tar.gz`

### 2. 傳輸到內網伺服器

透過 USB 或內部傳輸機制將 tar.gz 檔案複製到目標伺服器。

### 3. 內網伺服器安裝

```bash
# 解壓
tar -xzvf gms-helper-offline-*.tar.gz
cd gms-helper-offline

# 配置環境變數
cp .env.example .env
vi .env  # 填入 LLM API Token

# 一鍵安裝
./install-offline.sh
```

### 4. Cambrian LLM 連線測試 (推薦)

您可以在服務啟動後，進入容器的 bash 環境執行測試。

```bash
# 1. 進入容器 bash
docker exec -it gms-helper bash

# 2. (在容器內) 執行測試腳本
# 如果 .env 設定正確，可能不需要手動帶 token，但保險起見可以帶上
python scripts/test_cambrian.py --token YOUR_TOKEN
```

若看到 `✅ 所有測試通過！Cambrian 連線正常` 即代表部署成功。

---

## 配置 LLM Provider

### 方法一：透過 Web UI (推薦)

1. 開啟瀏覽器訪問 `http://<server-ip>:8000`
2. 點擊左側 **Settings**
3. 在 **AI Provider** 區塊選擇 **Cambrian**
4. 輸入您的 **API Token**
5. 選擇 **Model** (預設: LLAMA 3.3 70B)
6. 點擊 **Save Settings**

### 方法二：透過環境變數

在 `.env` 檔案中設定：

```bash
# LLM Provider: openai | internal | cambrian
LLM_PROVIDER=cambrian

# Cambrian Gateway
CAMBRIAN_URL=https://api.cambrian.pegatroncorp.com
CAMBRIAN_TOKEN=your-api-token
CAMBRIAN_MODEL=LLAMA 3.3 70B
```

---

## 常用命令

```bash
# 啟動服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 重啟服務
docker-compose restart

# 停止服務
docker-compose down

# 進入容器
docker exec -it gms-helper bash
```

---

## 故障排除

1. 確認網路與認證：
   ```bash
   curl -k -H "Authorization: Bearer <YOUR_TOKEN>" https://api.cambrian.pegatroncorp.com/v1/models
   ```
2. 確認 API Token 正確
3. 確認 SSL 驗證已關閉 (`INTERNAL_LLM_VERIFY_SSL=0`)

### 服務無法啟動

```bash
# 查看詳細日誌
docker-compose logs gms-helper

# 檢查容器狀態
docker ps -a
```
