# Run #6 分群分析報告 (Baseline)

> **目的**: 作為分群品質優化的基準線 (Baseline)，供後續改善後對照比較。

| 項目 | 內容 |
| :--- | :--- |
| 分析日期 | 2026-01-16 |
| 資料來源 | Run #6 (22 failures) |
| 演算法 | HDBSCAN + TF-IDF |
| 分析人員 | Chen Zeming |

---

## 1. 演算法執行指標

| 指標 | 數值 | 說明 |
| :--- | :--- | :--- |
| **演算法** | HDBSCAN | 密度型分群 |
| **樣本數 (n_samples)** | 22 | 失敗測試案例數 |
| **HDBSCAN 原始分群數** | 2 | 自動發現的密集區域 |
| **離群點數 (n_outliers)** | 5 | 無法歸類的樣本 |
| **離群點比例** | 22.7% | 偏高 |
| **輪廓係數 (Silhouette Score)** | **0.046** | ❌ 極低，接近隨機分配 |
| **TF-IDF 特徵維度** | 866 | 維度過高 |
| **後處理後分群數** | 6 | 經 Outlier Handling + Merge |

---

## 2. 分群結果詳情

### 2.1 群集摘要

| Cluster ID | Failure Count | Purity | 評價 |
| :--- | :--- | :--- | :--- |
| **19** | 6 | 0.33 | ⚠️ 混合群 |
| **20** | 11 | 0.20 | ❌ 雜物抽屜 |
| **21** | 1 | 1.00 | ✅ 純淨群 |
| **22** | 1 | 1.00 | ✅ 純淨群 |
| **23** | 2 | 1.00 | ✅ 純淨群 |
| **24** | 1 | 1.00 | ✅ 純淨群 |

### 2.2 Cluster 19 (6 failures, Purity: 0.33)

**涵蓋 Modules**: `CtsActivityRecognitionTestCases`, `CtsAutoFillServiceTestCases`, `CtsAppTestCases`

| Module | Class | Method |
| :--- | :--- | :--- |
| CtsActivityRecognitionTestCases | RenouncedPermissionsTest | testActivityRecognitionAttributionTagBlaming |
| CtsAppTestCases | ServiceTest | testMaxServiceConnections |
| CtsAppTestCases | ToolbarActionBarTest | testOptionsMenuKey |
| CtsAutoFillServiceTestCases | SessionLifecycleTest | testDatasetAuthResponseWhileAutofilledAppIsLifecycled |
| CtsAutoFillServiceTestCases | VirtualContainerActivityTest | testAutofill_appContext |
| CtsAutoFillServiceTestCases | InlineLoginActivityTest | testImeDisableInlineSuggestions_fallbackDropdownUi |

**例外類型**: `AssertionError`, `AssertionFailedError`, `RetryableException`

**AI 分類**: High Severity, Permission Issue

---

### 2.3 Cluster 20 (11 failures, Purity: 0.20) - ❌ 問題群集

**涵蓋 Modules**: `CtsAppCloningHostTest`, `CtsAppSecurityHostTestCases`, `CtsAdServicesPermissionsValidEndToEndTests`, `CtsAppDataIsolationHostTestCases`, `CtsBluetoothTestCases`

| Module | Class | Method |
| :--- | :--- | :--- |
| CtsAdServicesPermissionsValidEndToEndTests | PermissionsValidTest | testValidPermissions_fledgeJoinCustomAudience |
| CtsAppCloningHostTest | AppCloningHostTest | testGetStorageVolumesIncludingSharedProfiles |
| CtsAppCloningHostTest | AppCloningHostTest | testMediaCreationWithContentOwnerSpecifiedAsCloneUser |
| CtsAppCloningHostTest | AppCloningHostTest | testDeletionOfPrimaryApp_deleteAppWithParentPropertyTrue_deletesCloneApp |
| CtsAppCloningHostTest | AppCloningHostTest | testCrashingMediaProviderDoesNotAffectVolumeMounts |
| CtsAppCloningHostTest | AppCloningHostTest | testPrivateAppDataDirectoryForCloneUser |
| CtsAppCloningHostTest | AppCloningPublicVolumeTest | testCrossUserMediaAccessInPublicSdCard |
| CtsAppDataIsolationHostTestCases | AppDataIsolationTests | testAppUnableToAccessOtherUserAppDataDirApi29 |
| CtsAppSecurityHostTestCases | AppSecurityTests | testAppFailAccessPrivateData_full |
| CtsBluetoothTestCases | BluetoothAdapterTest | clearBluetooth (x2) |

**例外類型**: `AssertionError`, `ExecutionException`, `RuntimeException`, `TargetSetupError`

**AI 分類**: Medium Severity, Test Case Issue

**問題診斷**: 此群集是典型的「雜物抽屜」，混合了多個完全不同領域的失敗（App Cloning、Bluetooth、Security）。HDBSCAN 無法在現有特徵空間中區分它們。

---

### 2.4 純淨群集 (Clusters 21-24)

| Cluster | Module | Class | Method |
| :--- | :--- | :--- | :--- |
| **21** | CtsAppPredictionServiceTestCases | AppPredictionServiceTest | testRegisterPredictionUpdatesLifecycle |
| **22** | CtsBlobStoreTestCases | BlobStoreManagerTest | testCommitSession_multipleWrites |
| **23** | CtsAppFgsStartTestCases | ActivityManagerNewFgsLogicTest | testForCurrent |
| **23** | CtsAppFgsStartTestCases | ActivityManagerNewFgsLogicTest | testForApi34 |
| **24** | CtsAppOpsTestCases | DiscreteAppopsTest | testOpsListParameter |

這些群集被正確分離，代表了 Outlier Handling 後處理的成功案例。

---

## 3. 特徵分析

### 3.1 TF-IDF 特徵樣本 (前 50)

```
['001', '001 targetprep', '0x', '0x max', '10', '10 12', '10 doesn',
 '10 file_does_not_exist', '10 pkg', '100x100', '100x100 maxsize', '1012',
 '1012 caused', '1030', '106', '106 appsecurity', '109', '109 appcloning', '110',
 '111', '111 testtype', '12', '12 appcloningtestapp', '1279',
 '1279 autofillservice', '128', '128 toolbaractionbartest', '1283cb3dfec8',
 '1283cb3dfec8 ctsappcloninghosttest', '129', '129 activityrecognition',
 '133', '133 appsecurity', '137', '137 fgsstarttest', '137 testtype', '140',
 '140 autofillservice', '143', '151', '151 testtype', '160', '160 appsecurity',
 '169', '169 appsecurity', '182', '189', '189 compatibility', '190',
 '190 appcloning']
```

### 3.2 問題特徵

| 問題類型 | 範例 | 影響 |
| :--- | :--- | :--- |
| **行號噪音** | `106`, `129`, `137` | 無區分性，增加維度 |
| **路徑片段** | `0x`, `1283cb3dfec8` | 隨機 Hash，無意義 |
| **保留通用詞** | `appsecurity`, `testtype` | 雖有意義但過於頻繁 |

### 3.3 已過濾的停用詞

| 驗證項目 | 結果 |
| :--- | :--- |
| `assertionerror` in features? | ❌ False (已過濾) |
| `java` in features? | ❌ False (已過濾) |

---

## 4. 關鍵問題總結

| 問題 | 嚴重度 | 說明 |
| :--- | :--- | :--- |
| **輪廓係數極低** | 🔴 Critical | 0.046 接近隨機分配，群集無統計意義 |
| **維度災難** | 🟠 High | 866 維向量導致距離度量失效 |
| **Cluster 20 過大** | 🟠 High | 單一群集佔 50%，混合 5 個模組 |
| **語義缺失** | 🟡 Medium | TF-IDF 無法識別同義異詞 |

---

## 5. 後續改善方向

1.  **Phase 1**: 擴展停用詞 + 調參
2.  **Phase 2**: SVD 降維至 50-100 維
3.  **Phase 3**: 結構化特徵（Module/Class 權重）
4.  **Phase 4**: 語義嵌入 (Sentence-BERT / LLM Embedding)

> 詳見 `PRD_CLUSTERING_OPTIMIZATION.md`
