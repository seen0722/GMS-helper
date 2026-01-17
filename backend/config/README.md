# Module Owner Map 設定說明

## 檔案位置
`backend/config/module_owner_map.json`

---

## 用途

當使用 **Sync All** 或 **Smart Create** 建立 Redmine Issue 時，系統會根據此設定檔自動：
1. 根據 Module Name 決定指派給誰
2. 根據 AI Severity 決定 Priority
3. 使用預設的 Project ID

---

## 設定區塊

### 1. `module_patterns` - Module 對應規則

```json
"module_patterns": {
  "CtsMedia*": {
    "team_name": "Multimedia Team",    // 團隊名稱 (供參考)
    "redmine_user_id": 105,            // 直接指派給此 User
    "note": "Audio/Video related"      // 備註
  }
}
```

| 欄位 | 必填 | 說明 |
|:---|:---:|:---|
| key | ✅ | Glob pattern，支援 `*` 萬用字元 |
| `team_name` | ❌ | 團隊名稱，僅供參考 |
| `redmine_user_id` | ❌ | 指派給特定 User ID，`null` 表示不指派 |

**Pattern 範例：**
- `CtsMedia*` 匹配 `CtsMediaTestCases`, `CtsMediaCodecTestCases`
- `Cts*Camera*` 匹配任何含 Camera 的 Module

---

### 2. `team_to_user_map` - 團隊對應 User (可選)

```json
"team_to_user_map": {
  "Multimedia Team": 105,
  "Camera Team": 108,
  "Default": 55
}
```

當 `module_patterns` 的 `redmine_user_id` 為 `null` 時，會用 `team_name` 查這張表。

> **簡化建議：** 如果你偏好直接在 `module_patterns` 設定 `redmine_user_id`，這個區塊可以全部留 `null`。

---

### 3. `severity_to_priority` - Severity 對應 Priority

```json
"severity_to_priority": {
  "High": 5,      // Redmine Priority ID (例如: Immediate)
  "Medium": 4,    // High
  "Low": 3        // Normal
}
```

> 請根據你的 Redmine 實際 Priority ID 調整

---

### 4. `default_settings` - 預設值

```json
"default_settings": {
  "default_team": "Default",
  "default_priority_id": 4,
  "default_project_id": 1,      // Sync All 使用的 Project
  "fallback_user_id": 5         // 都沒匹配時的預設 Assignee
}
```

| 欄位 | 說明 |
|:---|:---|
| `default_project_id` | **Sync All 建立 Issue 的 Project** |
| `fallback_user_id` | 所有規則都沒匹配時的預設指派對象 |
| `default_priority_id` | Severity 沒設定時的預設 Priority |

---

## 指派優先順序

```
1. module_patterns[pattern].redmine_user_id  ← 最高優先
   ↓ 如果是 null
2. team_to_user_map[team_name]
   ↓ 如果沒匹配或是 null
3. default_settings.fallback_user_id         ← 最終 fallback
```

---

## 快速設定範例

### 最簡單的設定 (只用 fallback)

```json
{
  "module_patterns": {},
  "team_to_user_map": {},
  "default_settings": {
    "default_project_id": 1,
    "fallback_user_id": 55
  }
}
```
→ 所有 Issue 都指派給 User 55

### 按 Module 直接指派

```json
{
  "module_patterns": {
    "CtsMedia*": { "redmine_user_id": 105 },
    "CtsCamera*": { "redmine_user_id": 108 },
    "CtsWifi*": { "redmine_user_id": 110 }
  },
  "default_settings": {
    "default_project_id": 1,
    "fallback_user_id": 55
  }
}
```

---

## UI 設定

在 **Settings** 頁面的 **Module-Owner Assignment** 區塊：
1. 點擊 **Load from Redmine** 載入 Project 和 User 清單
2. 選擇 Default Project 和 Default Assignee
3. 可直接編輯 JSON 設定
4. 點擊 **Save Configuration** 儲存

---

## 如何取得 Redmine User ID

1. 登入 Redmine → Administration → Users
2. 點擊使用者 → URL 最後的數字就是 ID (如 `/users/105`)

或使用 API：
```bash
curl -H "X-Redmine-API-Key: YOUR_KEY" https://your-redmine.com/users.json
```
