# ML 系統策略：強化與說服計畫

## 1. 執行摘要：為什麼這套系統有效 (Executive Summary)
為了說服 Stakeholders（利害關係人），我們將討論重點從「它是否完美？」轉移到 **「是否具備高投資報酬率 (ROI)？」**

*   **問題痛點**：在 CI 流程中手動分類 (Triage) 超過 1,000 個以上的錯誤是完全不可能的任務。
*   **解決方案**：打造一個「分類助手」(Triage Assistant) 而非全自動駕駛，目標是降低工程師 80-90% 的認知負擔。
*   **數據佐證**：即使僅使用簡易的分群演算法，我們仍達到了 **~80% 的壓縮率** (92 個錯誤 → 僅需檢查 19 個)。

## 2. 技術驗證：如何證明有效 (Technical Validation)
在進行下一步強化之前，我們必須證明目前的基準線 (Baseline) 是穩定的。

### A. 量化指標 (硬數據)
我們需要透過 `verify_ai_accuracy.py` 自動追蹤並報告以下指標：
1.  **壓縮率 (Compression Ratio)**：$\frac{原始錯誤數 - 分群數}{原始錯誤數}$。越高越好 (代表效率高)。
2.  **分群純度 (Cluster Purity) [Precision]**：一個分群內的錯誤，是否真的全都屬於同一個問題？
    *   *評估方式*：「這些錯誤長得一樣嗎？」(驗證模式 2)。
    *   *商業價值*：「如果我修復了這個 Root Cause，是否能一次修好這群組內的所有錯誤？」
3.  **分群召回率 (Cluster Recall) [Fragmentation]**：同一個 Root Cause 是否被拆散到多個分群中？
    *   *評估方式*：較難自動量測。需要檢查 Cluster A 和 Cluster B 是否其實是重複的問題。
    *   *商業價值*：「我是否需要為了同一個 Bug 看 5 張不同的 Ticket？」
4.  **分類準確率 (Classification Accuracy)**：AI 預測的 Root Cause (Top-1) 是否正確。

#### 此情境下的 Precision (精確率) 與 Recall (召回率)
| 指標 (Metric) | 在分群應用 (Clustering) | 在分類應用 (Classification) |
| :--- | :--- | :--- |
| **Precision (精確率)** | **「純度 (Purity)」**：被分在一起的項目，真的是同一類嗎？ | **「可信度 (Trustworthiness)」**：AI 說是 Permission Issue，真的就是嗎？ |
| **Recall (召回率)** | **「完整性 (Completeness)」**：有沒有漏掉屬於這類別的項目？ | **「覆蓋率 (Coverage)」**：所有的 Permission Issue 當中，我們抓出了多少？ |

*> 註：Stakeholders 通常比較在意 Precision (不要浪費我的時間看錯誤的分群)，而比較能容忍 Recall 稍低 (同一個 Bug 被拆成兩個群組沒關係，只要不是漏掉就好)。*

### B. 質化指標 (Smoke Tests)
*   **穩定性 (Stability)**：輸入相同的錯誤 Log 兩次，是否會產生相同的分群結果？(決定性)
*   **離群值偵測 (Outlier Detection)**：系統標示為 "Unique" 的錯誤，是真的獨特錯誤，還是只是雜訊？

## 3. 強化藍圖：如何改進 (Enhancement Roadmap)
作為 ML 專家，我建議將系統從「第一代 (啟發式)」升級為「第二代 (語意式)」。

### 第一階段：語意分群 (Semantic Clustering) - *速效方案*
*   **現況**：使用 TF-IDF (關鍵字比對)。缺點是無法識別詞彙不同但語意相同的錯誤 (如 "Connection refused" vs "Socket closed")。
*   **升級**：導入 **SBERT (Sentence-BERT)** 或 OpenAI Embeddings。
*   **效益**：系統能理解 "Network error" 和 "Connection timeout" 是語意上相同的問題，大幅提升分群準確度。

### 第二階段：動態分群 (Dynamic K) - *智慧適應*
*   **現況**：使用啟發式 K 值 (樣本數 / 2)。
*   **升級**：改用 **DBSCAN** 或 **HDBSCAN** 演算法。
*   **效益**：無需猜測 `n_clusters` (分群數量)。演算法會自動找出自然的群組數量，並自動識別並過濾雜訊 (Outliers)。

### 第三階段：RAG 結合歷史知識庫 (Expert Memory) - *殺手級功能*
*   **現況**：AI 僅針對當下的錯誤進行獨立分析。
*   **升級**：建立向量資料庫 (Vector DB 如 Chroma/FAISS)，儲存過去 **已驗證** 的解決方案。
*   **效益**：「我們在兩個月前遇過這個問題 (Ticket #1234)，這是當時的解法。」-> 這將是說服 Stakeholders 的最強功能。

## 4. 給 Stakeholders 的說服腳本 (Persuasion Script)

**質疑者**：「我們能信任這個 AI 嗎？萬一它產生幻覺 (Hallucinations) 怎麼辦？」

**專家回應**：
> 「我們將此系統設計為 **「人機協作 (Human-in-the-Loop)」** 的加速器，而非盲目的自動駕駛。
>
> 1.  **安全至上 (Safety First)**：我們利用分群技術來歸納問題，但最終仍由**人類工程師**審閱代表性的錯誤。即使 AI 的摘要不完美，光是分群這個動作就已經幫您省去了重複檢查 49 次相同錯誤的時間。
> 2.  **透明度 (Transparency)**：我們明確顯示『信心分數 (Confidence Score)』。如果分數過低 (例如 2/5)，UI 會主動標示，提醒需要人工介入審查。
> 3.  **成本控制 (Cost Control)**：每次執行的成本僅約 $0.001 美金。相比之下，耗費工程師 2 小時的時間成本可能超過 $100 美金。其投資報酬率 (ROI) 高達 10,000%。」

## 5. 下一步行動 (Next Steps)
1.  **基準線**：使用 `verify_ai_accuracy.py` 完成真實數據的抽樣驗證。
2.  **原型開發**：建立 `experiment_semantic_clustering.py`，比較 TF-IDF 與 Embeddings 的效果差異。
