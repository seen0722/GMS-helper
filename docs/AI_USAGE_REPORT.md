# AI Analysis System: Token & Cost Usage Assessment

## 1. System Overview
The system uses a **two-stage hybrid approach** to analyze test failures, designed specifically to minimize costs while maintaining high-quality insights.

1.  **Stage 1: Local Clustering (Zero Cost)**
    *   Uses TF-IDF and K-Means clustering locally to group similar failures.
    *   **Impact**: Instead of analyzing 1,000 individual failures, the system only analyzes ~10-20 representative clusters.
    *   **Reduction Factor**: typically 90-99% reduction in API calls.

2.  **Stage 2: LLM Analysis (Low Cost)**
    *   Sends the representative failure from each cluster to OpenAI for analysis.
    *   **Model**: `gpt-4o-mini` (Cost-effective, high speed).

## 2. Token Usage Analysis

### Input (Prompt)
*   **System Prompt**: ~180 tokens (Fixed instructions on how to analyze Android failures).
*   **User Prompt**: Truncated to **3,000 characters** (approx. 750-1,000 tokens).
*   **Total Input**: **~1,000 - 1,200 tokens** per API call (maximum).

### Output (Response)
*   Format: JSON (Title, Summary, Root Cause, Solution, etc.).
*   **Estimated Size**: ~200 - 400 tokens per response.

## 3. Cost Analysis

**Model**: `gpt-4o-mini`
**Current Pricing** (Estimated):
*   Input: $0.15 / 1M tokens
*   Output: $0.60 / 1M tokens

### Per-Call Cost Estimate
| Component | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| **Input** | ~1,200 | ~$0.00018 |
| **Output** | ~300 | ~$0.00018 |
| **Total** | **~1,500** | **~$0.00036** |

**Cost per analysis is approximately $0.0004 (less than 1/20th of a cent).**

## 4. Scenario-Based Cost Projections

The clustering mechanism significantly decouples the *number of failures* from the *cost*.

| Scenario | Raw Failures | Clusters (API Calls) | Total Cost (Est.) |
| :--- | :--- | :--- | :--- |
| **Small Run** | 100 | ~5-10 | $0.002 - $0.004 |
| **Medium Run** | 1,000 | ~15-20 | $0.006 - $0.008 |
| **Large Run** | 10,000 | ~20 (Capped) | ~$0.008 |

*Note: The system caps the number of clusters (default max ~20), ensuring that even massive failure spikes do not cause cost explosions.*

## 5. Current Limitations & Recommendations

### Limitations
1.  **No Exact Tracking**: The database (`failure_analysis` table) stores the result but **does not store** the actual token usage (prompt_tokens, completion_tokens) returned by the OpenAI API.
2.  **Hard Coded Model**: The model `gpt-4o-mini` is hardcoded in `backend/analysis/llm_client.py`.

### Recommendations
1.  **Track Usage**: Add `prompt_tokens` and `completion_tokens` columns to the `failure_analysis` table to track exact costs over time.
2.  **Configurable Model**: Move the model name to the `Settings` table or environment variable to allow easy switching (e.g., to `gpt-4o` for tougher cases) without code changes.

## 6. Conclusion
The system is **highly optimized for cost**. By combining local clustering with the efficient `gpt-4o-mini` model, it achieves deep analysis capabilities for a negligible cost (fractions of a penny per test run).
