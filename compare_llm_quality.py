#!/usr/bin/env python3
"""
對比測試：Llama 3.1 8B vs GPT-4o 的 Root Cause 分析品質
"""

import json
import os
import sys
from openai import OpenAI

# 測試用的 failure 案例 (從 sample_cts.xml 提取)
TEST_FAILURES = [
    {
        "name": "Permission Denial",
        "context": """
Test Failure Details:
- Module: CtsPermissionTestCases
- Test Class: android.permission.cts.PermissionTest
- Test Method: testCameraPermission
- Error Message: java.lang.SecurityException: Permission Denial: starting activity requires android.permission.CAMERA
- Stack Trace: 
    at android.app.ContextImpl.startActivityAsUser(ContextImpl.java:1134)
    at android.content.ContextWrapper.startActivity(ContextWrapper.java:390)
    at android.permission.cts.PermissionTest.testCameraPermission(PermissionTest.java:87)
"""
    },
    {
        "name": "Timeout Issue",
        "context": """
Test Failure Details:
- Module: CtsMediaTestCases
- Test Class: android.media.cts.MediaCodecTest
- Test Method: testDecodeH264
- Error Message: junit.framework.AssertionFailedError: Decoder did not return output within 5000ms timeout
- Stack Trace:
    at android.media.cts.MediaCodecTest.waitForOutput(MediaCodecTest.java:234)
    at android.media.cts.MediaCodecTest.testDecodeH264(MediaCodecTest.java:156)
"""
    },
    {
        "name": "Complex Framework Bug",
        "context": """
Test Failure Details:
- Module: CtsContentTestCases
- Test Class: android.content.cts.ContentProviderTest
- Test Method: testContentObserverNotification
- Error Message: java.lang.IllegalStateException: Cannot perform this operation because the connection has been closed
- Stack Trace:
    at android.database.sqlite.SQLiteConnectionPool.throwIfClosedLocked(SQLiteConnectionPool.java:1127)
    at android.database.sqlite.SQLiteConnectionPool.waitForConnection(SQLiteConnectionPool.java:653)
    at android.database.sqlite.SQLiteSession.beginTransaction(SQLiteSession.java:347)
    at android.content.ContentProvider.openAssetFile(ContentProvider.java:1456)
    at android.content.cts.ContentProviderTest.testContentObserverNotification(ContentProviderTest.java:389)
- Number of similar failures in cluster: 12
"""
    }
]

SYSTEM_PROMPT = """You are an expert Android GMS certification test engineer. Analyze test failures and provide actionable insights.

Return a JSON response with the following keys:
- 'title': A single, descriptive sentence summarizing the failure (max 20 words).
- 'root_cause': A concise technical explanation of why the test failed.
- 'solution': Specific, actionable steps to fix the issue.
- 'severity': One of "High", "Medium", "Low".
- 'category': Choose from: "Test Case Issue", "Framework Issue", "Media/Codec Issue", "Permission Issue", "Configuration Issue", "Hardware Issue", "Performance Issue", "System Stability".
- 'confidence_score': An integer from 1 to 5."""


def analyze_with_model(client: OpenAI, model: str, failure_context: str) -> dict:
    """使用指定模型分析 failure"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this test failure:\n\n{failure_context}"}
            ],
            response_format={"type": "json_object"} if "gpt" in model else None,
        )
        content = response.choices[0].message.content
        # Try to parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                return json.loads(match.group())
            return {"raw_response": content[:500]}
    except Exception as e:
        return {"error": str(e)}


def main():
    # Setup clients
    ollama_client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed")
    
    # Check for OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        # Try to get from database
        try:
            sys.path.insert(0, '/Users/chenzeming/dev/GMS-helper')
            from backend.database.database import SessionLocal
            from backend.database import models
            from backend.utils import encryption
            db = SessionLocal()
            setting = db.query(models.Settings).first()
            if setting and setting.openai_api_key:
                openai_key = encryption.decrypt(setting.openai_api_key)
            db.close()
        except Exception as e:
            print(f"Warning: Could not get OpenAI key from DB: {e}")
    
    openai_client = OpenAI(api_key=openai_key) if openai_key else None
    
    print("=" * 80)
    print("🔬 LLM Analysis Quality Comparison: Llama 3.1 8B vs GPT-4o-mini")
    print("=" * 80)
    
    for failure in TEST_FAILURES:
        print(f"\n{'─' * 80}")
        print(f"📋 Test Case: {failure['name']}")
        print(f"{'─' * 80}")
        
        # Llama 3.1 8B
        print("\n🦙 Llama 3.1 8B (Ollama):")
        llama_result = analyze_with_model(ollama_client, "llama3.1:latest", failure["context"])
        print(f"  Title: {llama_result.get('title', 'N/A')}")
        print(f"  Root Cause: {llama_result.get('root_cause', 'N/A')[:200]}...")
        print(f"  Solution: {llama_result.get('solution', 'N/A')[:200]}...")
        print(f"  Severity: {llama_result.get('severity', 'N/A')}, Confidence: {llama_result.get('confidence_score', 'N/A')}")
        
        # GPT-4o-mini
        if openai_client:
            print("\n🤖 GPT-4o-mini (OpenAI):")
            gpt_result = analyze_with_model(openai_client, "gpt-4o-mini", failure["context"])
            print(f"  Title: {gpt_result.get('title', 'N/A')}")
            print(f"  Root Cause: {gpt_result.get('root_cause', 'N/A')[:200]}...")
            print(f"  Solution: {gpt_result.get('solution', 'N/A')[:200]}...")
            print(f"  Severity: {gpt_result.get('severity', 'N/A')}, Confidence: {gpt_result.get('confidence_score', 'N/A')}")
        else:
            print("\n⚠️  GPT-4o-mini: Skipped (no API key)")
    
    print(f"\n{'=' * 80}")
    print("✅ Comparison Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
