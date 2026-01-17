# PRD: Redmine 智慧自動提單策略 (Smart Redmine Automation Strategy)

## 1. 核心理念 (Core Philosophy)

站在 BSP Tech Leader 的角度，自動化提單系統成功的關鍵在於**「降噪 (Noise Reduction)」**與**「精準 (Accuracy)」**。系統不應成為製造垃圾工單 (Spam) 的機器，而應成為協助 RD 快速定位問題的助手。

**核心原則：Cluster-First Strategy (叢集優先)**
*   **禁止**針對單一 Test Case Failure 提單。
*   **必須**基於 AI 分析後的 Cluster 進行提單。
*   **目標**：1 個 Root Cause = 1 張 Redmine Ticket。

---

## 2. 提單策略：以模組為中心 (Module-Centric Filing)

為了解決 "Root Cause 跨模組" 與 "團隊分工以模組為界" 的矛盾，本 PRD 採用 **「強制拆分 (Strict Module Splitting)」** 策略。

### 2.1 策略邏輯
即使 AI 發現一個 Cluster (例如 #5: "Audio Buffer Underrun") 橫跨多個模組 (例如 `CtsMedia` 和 `CtsTelecom`)，系統在提單時**強制拆分**為多張工單。

*   **Cluster #5 (Root Cause: Audio Buffer)**
    *   Ticket A: `[GMS][CtsMedia] Audio Buffer Underrun` -> Assign to Audio Team
    *   Ticket B: `[GMS][CtsTelecom] Audio Buffer Underrun` -> Assign to Telecom Team

**理由**:
1.  **組織權責一致**: 避免跨部門推諉 (Ping-pong)。
2.  **UI 一致性**: 確保 Module View 中的所有工單都屬於該 Module。

### 2.2 多重 Cluster 顯示 (Multi-Cluster Representation)
當單一 Module 包含多個不同的 Cluster 時，UI 應呈現階層結構。

```text
▼ CtsMediaTestCases (Module Card)                [Total: 45 Failures]  [P0]
  |
  |-- ■ Ticket A: AudioTrack Buffer Underrun     [30 Failures]  [High]  (Cluster #5)
  |     (Status: New | Assign: Audio Team)
  |
  |-- ■ Ticket B: MediaCodec Decode Error        [15 Failures]  [Medium] (Cluster #12)
        (Status: Resolved | Assign: Video Team)
```

**顯示邏輯**:
*   **Module Card**: 聚合顯示該 Module 下所有 Cluster 的失敗總和及最高 Severity。
*   **Cluster Row**: 顯示該 Cluster 在此 Module 內的局部失敗數 (Local Fail count)。

---

## 3. 智慧工作流 (Smart Workflow)

系統應具備「智慧去重」與「生命週期管理」能力，而非單純的單向拋送。

### 2.1 流程圖

```mermaid
graph TD
    A[XML 上傳 & AI 分群] --> B{檢查 Redmine 重複工單}
    B -->|發現 Open 工單| C[更新模式 (Update Mode)]
    B -->|發現 Closed 工單| D[回歸模式 (Regression Mode)]
    B -->|無重複| E[新建模式 (Create Mode)]
    
    subgraph Update Mode
    C --> C1[新增 Note: "Issue reproduced in build <Build_ID>"]
    C --> C2[更新 Custom Fields: <Fail_Count>, <Last_Seen_Build>]
    end
    
    subgraph Regression Mode
    D --> D1[Reopen Issue]
    D --> D2[設定 Priority = High]
    D --> D3[新增 Note: "Regression detected in build <Build_ID>"]
    end
    
    subgraph Create Mode
    E --> E1[生成標準化標題 & 內容]
    E --> E2[自動分派 (Assignment Matrix)]
    E --> E3[設定 Priority]
    end
```

### 2.2 去重機制 (Deduplication Logic)
*   **Search Key**: 使用 Cluster 的 `Signature` (Stack Trace Hash) 或 `Module Name` + `Error Type` 組合進行搜尋。
*   **判定標準**: 標題相似度 > 80% 或 Signature 精確匹配。

---

## 3. 工單內容標準 (Ticket Template)

所有自動/半自動建立的工單必須遵循以下格式，確保 RD 擁有修解所需的一切資訊。

### 3.1 標題格式 (Subject)
```text
[GMS][<Android_Version>][<Module_Name>] <AI_Summary>
```
*   **範例**: `[GMS][14][CtsMediaTestCases] AudioTrack timestamp mismatch causing buffer underrun`

### 3.2 內容格式 (Description)
使用 Markdown 格式，包含以下區塊：

```markdown
**[AI Analysis]**
*   **Root Cause**: <AI_Root_Cause>
*   **Impact**: 共 <Fail_Count> 個測項失敗 (關聯 Cluster ID: #<Cluster_ID>)
*   **Suggestion**: <AI_Solution>

**[Environment]**
*   **Project**: <Build_Product>
*   **Build ID**: <Build_ID>
*   **Fingerprint**: <Device_Fingerprint>
*   **Suite Version**: <Suite_Version>

**[Representative Failure]**
*   **Test Class**: <Class_Name>
*   **Test Method**: <Method_Name>
*   **Error Message**:
    ```
    <Error_Message>
    ```
*   **Stack Trace (Top 50 lines)**:
    ```java
    <Stack_Trace>
    ```

**[Affected Tests (Top 10)]**
1. <Test_Case_1>
2. <Test_Case_2>
...
```

---

## 4. 自動分派矩陣 (Assignment Matrix)

建立 `Module_Owner_Map`，根據 Module Name 前綴自動分派給對應團隊。

| Module Pattern | Target Team | Note |
| :--- | :--- | :--- |
| `CtsMedia*` | Multimedia Team | Audio/Video 相關 |
| `CtsCamera*` | Camera Team | |
| `CtsWifi*`, `CtsNet*`, `CtsBluetooth*` | Connectivity Team | |
| `CtsSystemUi*`, `CtsView*` | Framework Team | UI 相關 |
| `CtsKernel*`, `CtsFs*` | BSP/Kernel Team | 底層驅動/檔案系統 |
| `CtsSecurity*` | Security Team | |
| `*` (Default) | System QA / GMS Owners | 無法歸類者 |

---

## 5. 實施階段規劃 (Implementation Roadmap)

### Phase 1: 輔助提單模式 (Assisted Mode) - *Current Target*
*   **機制**: 用戶點擊 "Create Issue" -> 彈出 Modal -> 系統預填好上述標準 Template -> 用戶確認/修改 -> 提交。
*   **目標**: 建立標準化工單，減少人工 Copy-Paste 時間。

### Phase 2: 自動備註模式 (Auto-Comment Mode)
*   **機制**: 系統在背景掃描。若發現相同 Cluster 已有對應工單，自動在該工單下留言 "Reproduced in build XYZ"。
*   **目標**: 減少重複工單 (Duplicate Tickets)，轉而累積現有工單的證據力。

### Phase 3: 全自動 regression 偵測 (Regression Guard)
*   **機制**: 若發現已 Close 的工單對應的 Cluster 再次出現，自動 Reopen 並通知相關人員。
*   **目標**: 防止已修復問題回歸 (Regression)。

### Phase 4: 高信心全自動提單 (Fully Autonomous)
*   **機制**: 僅當 `Confidence Score > 4` (高信心) 且 `Severity = High` 時，系統才自動建立新工單，無需人工介入。
*   **目標**: 實現無人值守的 Nightly Run Triage。

---

## 6. 風險控管 (Risk Management)

| 風險 | 緩解措施 |
| :--- | :--- |
| **Notification Spam** (通知轟炸) | 實作 Rate Limiting，同一小時內對同一 Assignee 發送不超過 N 封通知；善用 "Update" 而非 "Create"。 |
| **False Positives** (誤判) | 初期僅由人工審核 (Phase 1)，AI 信心分數需經校準後才開啟自動化。 |
| **Redmine API 限制** | 實作 Queue 機制與 Retry 邏輯，避免併發過高拖垮 Redmine。 |
