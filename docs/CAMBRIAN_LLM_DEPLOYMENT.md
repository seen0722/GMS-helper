# CTS Insight × Cambrian LLM 內網部署指南

本文件說明如何在 Pegatron 內網伺服器上部署 CTS Insight，並整合 Cambrian LLM Gateway 進行 AI 分析。

---

## 架構概覽

```
┌─────────────────────┐     HTTPS (SSL skip)     ┌─────────────────────────────┐
│   CTS Insight       │ ────────────────────────▶│  Cambrian LLM Gateway       │
│   (Docker)          │                          │  api.cambrian.pegatroncorp.com
│                     │                          │                             │
│   :8000             │                          │  Models:                    │
│   SQLite DB         │                          │    - LLAMA 3.3 70B          │
│   FastAPI + Uvicorn │                          │    - LLAMA 3.1 8B           │
└─────────────────────┘                          │    - Qwen 2.5               │
                                                 └─────────────────────────────┘
```

---

## 快速部署（Docker Hub）

### 1. 環境需求

| 項目 | 版本 | 說明 |
|------|------|------|
| OS | Ubuntu 20.04+ / CentOS 8+ | 或其他支援 Docker 的系統 |
| Docker | 20.10+ | 容器運行環境 |
| Docker Compose | v2.x | 多容器管理 |
| 記憶體 | 2GB+ | 用於 AI 分析時的文字處理 |
| 網路 | 可連接 `api.cambrian.pegatroncorp.com` | Cambrian Gateway |

### 2. 取得 Cambrian API Token

1. 登入 Cambrian Portal: `https://cambrian.pegatroncorp.com`
2. 前往 **API Keys** 頁面
3. 產生新的 Token，妥善保存

### 3. 部署步驟

```bash
# 1. 建立專案目錄
mkdir cts-insight && cd cts-insight

# 2. 建立 docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  cts-insight:
    image: seen0516/gms-helper:latest
    container_name: cts-insight
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    environment:
      - DATABASE_URL=sqlite:///./data/gms_analysis.db
      - LLM_PROVIDER=cambrian
      - CAMBRIAN_URL=https://api.cambrian.pegatroncorp.com
      - CAMBRIAN_MODEL=LLAMA 3.3 70B
      # Token 透過 UI 設定更安全，或在此填入：
      # - CAMBRIAN_TOKEN=your-token-here
EOF

# 3. 建立資料目錄
mkdir -p data uploads

# 4. 啟動服務
docker-compose up -d

# 5. 確認運行
curl http://localhost:8000/api/health
```

### 4. 首次設定

開啟瀏覽器 → `http://<server-ip>:8000` → 點擊 **Settings**

#### AI Settings（AI 分析）

| 欄位 | 值 | 說明 |
|------|-----|------|
| AI Provider | `Cambrian` | 選擇 Cambrian |
| API Token | `your-token` | 從 Cambrian Portal 取得 |
| Model | `LLAMA 3.3 70B` | 點擊 🔄 刷新可用模型 |

→ 點擊 **Test Connection** 驗證 → **Save Settings**

#### General Settings（應用程式設定）

| 欄位 | 值 | 說明 |
|------|-----|------|
| Application Base URL | `http://<server-ip>:8000` | 用於生成 Redmine Issue 中的連結 |

→ 點擊 **Save**

#### Redmine Integration（Issue 追蹤）

| 欄位 | 值 | 說明 |
|------|-----|------|
| Redmine URL | `http://your-redmine-server` | Redmine 主機位址 |
| API Key | `your-redmine-api-key` | 從 Redmine 個人設定取得 |

→ 點擊 **Test** 驗證 → **Save**

> **取得 Redmine API Key**：登入 Redmine → 右上角「我的帳戶」→ API 存取金鑰 → 顯示

---


## Cambrian LLM 設定

### 方法一：透過 Web UI（推薦）

1. 開啟瀏覽器 → `http://<server-ip>:8000`
2. 點擊左側 **Settings**
3. 在 **AI Provider** 選擇 **Cambrian**
4. 填入設定：

| 欄位 | 值 | 說明 |
|------|-----|------|
| API Token | `your-token` | 從 Cambrian Portal 取得 |
| Model | `LLAMA 3.3 70B` | 點擊 🔄 可刷新可用模型 |

5. 點擊 **Test Connection** 驗證
6. 點擊 **Save Settings**

### 方法二：環境變數設定

建立 `.env` 檔案：

```bash
# LLM Provider
LLM_PROVIDER=cambrian

# Cambrian Gateway
CAMBRIAN_URL=https://api.cambrian.pegatroncorp.com
CAMBRIAN_TOKEN=your-api-token-here
CAMBRIAN_MODEL=LLAMA 3.3 70B
```

然後重啟服務：

```bash
docker-compose down && docker-compose up -d
```

---

## 連線測試

### 方法一：UI 測試

Settings → **Test Connection** → 應顯示 ✅ Connected

### 方法二：命令列測試

```bash
# 進入容器
docker exec -it gms-helper bash

# 執行測試腳本
python scripts/test_cambrian.py --token YOUR_TOKEN
```

成功輸出：
```
==============================================
Cambrian LLM Gateway 連線測試
==============================================
[1/3] 測試 HTTP 連線...
      ✅ HTTP 連線成功
      可用模型:
        - LLAMA 3.3 70B
        - LLAMA 3.1 8B Instruct
        ...

[2/3] 初始化 OpenAI Client...
      ✅ Client 初始化成功

[3/3] 測試 LLM 回應...
      ✅ 成功! 回應: Hello

==============================================
✅ 所有測試通過！Cambrian 連線正常。
==============================================
```

### 方法三：curl 直接測試

```bash
# 測試 Cambrian 模型列表 API
curl -k -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.cambrian.pegatroncorp.com/assistant/llm_model
```

---

## 技術細節

### API 端點對應

| 功能 | Cambrian 端點 |
|------|---------------|
| 模型列表 | `GET /assistant/llm_model` |
| Chat Completions | `POST /v1/chat/completions` |

### SSL 處理

Cambrian 內網使用自簽憑證，系統已自動跳過驗證：

```python
# backend/analysis/llm_client.py
http_client = httpx.Client(verify=False)  # 跳過 SSL 驗證
```

### 支援的模型

| 模型名稱 | 用途 | 回應速度 |
|----------|------|----------|
| `LLAMA 3.3 70B` | 高品質分析（推薦）| 較慢 |
| `LLAMA 3.1 8B Instruct` | 快速回應 | 快 |
| `Qwen 2.5` | 中文優化 | 中等 |

---

## 故障排除

### 1. Connection Refused

```bash
# 檢查網路連通性
ping api.cambrian.pegatroncorp.com
curl -k https://api.cambrian.pegatroncorp.com/health
```

### 2. 401 Unauthorized

- 確認 Token 正確
- Token 可能已過期，需在 Cambrian Portal 重新產生

### 3. Analysis 卡住

```bash
# 查看日誌
docker-compose logs -f gms-helper

# 常見原因：
# - Token 未設定
# - 模型名稱錯誤
# - Cambrian 服務暫時不可用
```

### 4. 測試成功但分析失敗

確認 Settings 中的 Token 已儲存（加密）：

```bash
docker exec gms-helper python -c "
from backend.database.database import SessionLocal
from backend.database import models
db = SessionLocal()
s = db.query(models.Settings).first()
print(f'Provider: {s.llm_provider}')
print(f'Token set: {bool(s.cambrian_token)}')
"
```

---

## 常用命令

```bash
# 啟動
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 重啟
docker-compose restart

# 停止
docker-compose down

# 進入容器 shell
docker exec -it gms-helper bash

# 備份資料庫
cp data/gms_analysis.db backup/gms_analysis_$(date +%Y%m%d).db
```

---

## 安全注意事項

| 項目 | 建議 |
|------|------|
| API Token | 不要 commit 到 git，使用 `.env` 或 secrets |
| 正式部署 | 移除 `--reload` 和 `./backend` volume mount |
| 存取控制 | 部署防火牆限制 8000 port 存取來源 |

---

## 相關文件

- [離線部署指南](OFFLINE_DEPLOYMENT.md)
- [架構說明](ARCHITECTURE.md)
- [API 文件](http://localhost:8000/docs)
