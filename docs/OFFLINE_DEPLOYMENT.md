# 離線部署指南 (Air-Gapped Deployment)

本文件說明如何在無外部網路的內網伺服器上部署 GMS-Helper。

## 環境需求

**目標伺服器 (Offline Server)**
*   OS: Linux (Ubuntu 20.04+, CentOS 7+, etc.)
*   Docker: 20.10+
*   Docker Compose: v2.x

**開發/打包機 (Online Machine)**
*   Docker & Docker Compose installed
*   GMS-Helper source code

---

## 部署流程

### 1. 打包 (在開發機執行)

在有網路的機器上執行打包腳本，這會建立一個包含所有 Docker images 和設定檔的壓縮包。

```bash
cd /path/to/GMS-helper
./scripts/package-offline.sh
```

成功後會產生一個檔案：`gms-helper-offline-YYYYMMDD-HHMMSS.tar.gz`

### 2. 傳輸 (SCP)

將產生的 `.tar.gz` 檔案傳輸到內網伺服器。

```bash
# 範例
scp gms-helper-offline-20260113-xxxxxx.tar.gz user@192.168.x.x:/home/user/deploy/
```

### 3. 安裝與啟動 (在內網伺服器執行)

登入內網伺服器並執行以下步驟：

```bash
# 1. 解壓縮
tar -xzvf gms-helper-offline-*.tar.gz

# 2. 進入目錄
cd gms-helper-offline-*

# 3. 執行安裝腳本
# 此腳本會：
#   - 載入 docker images (docker load)
#   - 建立 .env 設定檔 (如果不存在)
#   - 啟動服務 (docker-compose up -d)
./install.sh
```

**設定 API Key:**
安裝腳本會自動產生 `.env` 檔。請編輯它並填入您的 Cambrian API Key：

```bash
vi .env
# 修改 INTERNAL_LLM_API_KEY=your_actual_token_here
```

修改後重啟服務：
```bash
docker-compose restart
```

---

## 驗證與測試

### 1. 服務狀態檢查

```bash
docker-compose ps
# 預期 output:
# NAME         IMAGE               STATUS              PORTS
# gms-helper   gms-helper:latest   Up (healthy)        0.0.0.0:8000->8000/tcp
```

### 2. Cambrian LLM 連線測試 (推薦)

我們提供了一個測試工具，可以直接在容器內環境執行，驗證網路與 API Key 是否正確。

**方式 A: 使用 docker-compose (最簡單)**

```bash
# 確保已在 .env 設定好 INTERNAL_LLM_API_KEY
docker-compose --profile test run --rm test-runner
# 進入後執行：
python scripts/test_cambrian.py --token $INTERNAL_LLM_API_KEY
```

**方式 B: 直接在執行中的容器測試**

```bash
docker exec -it gms-helper python scripts/test_cambrian.py --token <YOUR_TOKEN>
```

若看到 `✅ 所有測試通過！Cambrian 連線正常` 即代表部署成功。

---

## 常見問題

### Q: `install.sh` 執行失敗，說找不到 `docker` 指令？
A: 請確認您的使用者有執行 docker 的權限，或使用 `sudo ./install.sh`。

### Q: `docker-compose` 版本過舊？
A: 如果伺服器上只有舊版 `docker-compose` (Python版)，指令可能不同。我們的腳本預設使用 Docker Compose v2 (`docker compose` 或 `docker-compose`)。如果遇到問題，請手動執行：
```bash
docker load < images.tar
docker-compose up -d
```

### Q: 測試腳本連線失敗 (ConnectTimeout)？
A: 請確認伺服器防火牆是否允許連線至 `api.cambrian.pegatroncorp.com` (Port 443)。
