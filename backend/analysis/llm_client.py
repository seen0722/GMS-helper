from abc import ABC, abstractmethod
import os
# import openai # Uncomment when ready

import json
from openai import OpenAI

class LLMClient(ABC):
    @abstractmethod
    def analyze_failure(self, failure_text: str) -> dict:
        pass

class MockLLMClient(LLMClient):
    def analyze_failure(self, failure_text: str) -> dict:
        return {
            "root_cause": "Mock Analysis: This failure seems to be caused by a timing issue.",
            "solution": "Suggest increasing timeout or checking device load.",
            "ai_summary": "Timing issue detected in test execution.",
            "severity": "Medium",
            "category": "System Stability",
            "confidence_score": 3,
            "suggested_assignment": "System Team"
        }

class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analyze_failure(self, failure_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are an expert Android GMS certification test engineer. Analyze test failures and provide actionable insights.

When analyzing failures:
- Focus on the error message, test class, and method name if stack trace is limited
- Provide specific, actionable root causes based on the test context
- Suggest concrete solutions that developers can implement
- If the failure is about timing, media codecs, or framework issues, provide relevant Android-specific guidance

Return a JSON response with the following keys:
- 'title': A single, descriptive sentence summarizing the failure (e.g., "Assertion failure due to improper default permission grants"). Max 20 words. Do NOT use markdown.
- 'summary': A detailed technical summary of the failure.
- 'root_cause': A concise technical explanation of why the test failed.
- 'solution': Specific, actionable steps to fix the issue.
- 'severity': One of "High", "Medium", "Low". High = Crash/Fatal/Blocker.
- 'category': The main category of the error. Choose from: "Test Case Issue", "Framework Issue", "Media/Codec Issue", "Permission Issue", "Configuration Issue", "Hardware Issue", "Performance Issue", "System Stability".
- 'confidence_score': An integer from 1 to 5 (5 is highest confidence).
- 'suggested_assignment': The likely team or component owner (e.g., "Audio Team", "Camera Team", "Framework Team")."""},
                    {"role": "user", "content": f"Analyze this test failure:\n\n{failure_text[:3000]}"} # Increased limit for more context
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Combine title and summary for backward compatibility and frontend display
            if 'title' in result and 'summary' in result:
                result['ai_summary'] = f"{result['title']}\n{result['summary']}"
            elif 'title' in result:
                 result['ai_summary'] = result['title']
            elif 'summary' in result:
                 result['ai_summary'] = result['summary']
                 
            return result
        except Exception as e:
            print(f"OpenAI API call failed: {e}")
            return {
                "root_cause": "AI Analysis Failed",
                "solution": f"Error: {str(e)}",
                "ai_summary": "Analysis failed due to API error.",
                "severity": "Low",
                "category": "Unknown",
                "confidence_score": 1,
                "suggested_assignment": "Unknown"
            }

def get_llm_client():
    """Get LLM client using stored API key from database or environment variable."""
    from backend.database.database import SessionLocal
    from backend.database import models
    from backend.utils import encryption
    
    api_key = None
    
    # Try to get from database first
    try:
        db = SessionLocal()
        setting = db.query(models.Settings).first()
        if setting and setting.openai_api_key:
            api_key = encryption.decrypt(setting.openai_api_key)
        db.close()
    except Exception as e:
        print(f"Error fetching API key from database: {e}")
    
    # Fall back to environment variable
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
        
    if api_key:
        return OpenAILLMClient(api_key)
    return MockLLMClient()
