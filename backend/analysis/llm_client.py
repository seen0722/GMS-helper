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

SYSTEM_PROMPT = """You are an expert Android GMS certification test engineer. Analyze test failures and provide actionable insights.

When analyzing failures:
- Focus on the error message, test class, and method name if stack trace is limited
- Provide specific, actionable root causes based on the test context
- Suggest concrete solutions that developers can implement
- If the failure is about timing, media codecs, or framework issues, provide relevant Android-specific guidance

Return a JSON response with the following keys:
- 'title': A single, descriptive sentence summarizing the failure (e.g., "Assertion failure due to improper default permission grants"). Max 20 words. Do NOT use markdown.
- 'summary': A detailed technical summary of the failure.
- 'root_cause': A concise technical explanation of why the test failed. If multiple causes, use numbered list with each item on a new line (e.g., "1. First cause\\n2. Second cause").
- 'solution': Specific, actionable steps to fix the issue. IMPORTANT: Use numbered list with each step on a NEW LINE separated by \\n (e.g., "1. First step\\n2. Second step\\n3. Third step"). Do NOT put all steps on one line.
- 'severity': One of "High", "Medium", "Low". High = Crash/Fatal/Blocker.
- 'category': The main category of the error. Choose from: "Test Case Issue", "Framework Issue", "Media/Codec Issue", "Permission Issue", "Configuration Issue", "Hardware Issue", "Performance Issue", "System Stability".
- 'confidence_score': An integer from 1 to 5 (5 is highest confidence).
- 'suggested_assignment': The likely team or component owner (e.g., "Audio Team", "Camera Team", "Framework Team")."""


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analyze_failure(self, failure_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this test failure:\n\n{failure_text[:3000]}"}
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


class InternalLLMClient(LLMClient):
    """LLM client for internal Ollama/vLLM servers with OpenAI-compatible API."""
    
    def __init__(self, base_url: str, model: str = "llama3.1:8b", api_key: str = "not-needed"):
        """
        Initialize internal LLM client.
        
        Args:
            base_url: The base URL of the LLM server (e.g., http://localhost:11434/v1)
            model: The model name to use (e.g., llama3.1:8b, qwen2.5:7b)
            api_key: API key (usually not required for internal servers)
        """
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.base_url = base_url

    def analyze_failure(self, failure_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this test failure:\n\n{failure_text[:3000]}"}
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
            print(f"Internal LLM API call failed ({self.base_url}): {e}")
            return {
                "root_cause": "AI Analysis Failed",
                "solution": f"Error connecting to internal LLM: {str(e)}",
                "ai_summary": "Analysis failed due to internal LLM error.",
                "severity": "Low",
                "category": "Unknown",
                "confidence_score": 1,
                "suggested_assignment": "Unknown"
            }
class CambrianLLMClient(LLMClient):
    """LLM client for Cambrian internal gateway with SSL verification disabled."""
    
    def __init__(self, base_url: str, api_key: str, model: str = "LLAMA 3.3 70B"):
        """
        Initialize Cambrian LLM client.
        
        Args:
            base_url: The Cambrian API URL (e.g., https://api.cambrian.pegatroncorp.com)
            api_key: Cambrian API token
            model: The model name to use (e.g., LLAMA 3.3 70B)
        """
        import httpx
        # Disable SSL verification for internal network
        http_client = httpx.Client(verify=False)
        self.client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
        self.model = model
        self.base_url = base_url

    def analyze_failure(self, failure_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this test failure:\n\n{failure_text[:3000]}"}
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
            print(f"Cambrian LLM API call failed ({self.base_url}): {e}")
            return {
                "root_cause": "AI Analysis Failed",
                "solution": f"Error connecting to Cambrian: {str(e)}",
                "ai_summary": "Analysis failed due to Cambrian API error.",
                "severity": "Low",
                "category": "Unknown",
                "confidence_score": 1,
                "suggested_assignment": "Unknown"
            }


def get_llm_client():
    """Get LLM client based on stored settings - supports OpenAI, Internal (Ollama/vLLM), Cambrian, or Mock."""
    from backend.database.database import SessionLocal
    from backend.database import models
    from backend.utils import encryption
    
    try:
        db = SessionLocal()
        setting = db.query(models.Settings).first()
        
        if setting:
            provider = getattr(setting, 'llm_provider', 'openai') or 'openai'
            
            # Cambrian LLM
            if provider == 'cambrian':
                cambrian_url = getattr(setting, 'cambrian_url', None)
                cambrian_token = getattr(setting, 'cambrian_token', None)
                cambrian_model = getattr(setting, 'cambrian_model', 'LLAMA 3.3 70B') or 'LLAMA 3.3 70B'
                
                if cambrian_url and cambrian_token:
                    try:
                        decrypted_token = encryption.decrypt(cambrian_token)
                        db.close()
                        return CambrianLLMClient(base_url=cambrian_url, api_key=decrypted_token, model=cambrian_model)
                    except Exception as e:
                        print(f"Error decrypting Cambrian token: {e}")
                        db.close()
                        return MockLLMClient()
                else:
                    print("Cambrian URL or token not configured, falling back to Mock")
                    db.close()
                    return MockLLMClient()
            
            # Internal LLM (Ollama/vLLM)
            elif provider == 'internal':
                internal_url = getattr(setting, 'internal_llm_url', None)
                internal_model = getattr(setting, 'internal_llm_model', 'llama3.1:8b') or 'llama3.1:8b'
                
                if internal_url:
                    db.close()
                    return InternalLLMClient(base_url=internal_url, model=internal_model)
                else:
                    print("Internal LLM URL not configured, falling back to Mock")
                    db.close()
                    return MockLLMClient()
            
            # OpenAI
            elif provider == 'openai':
                if setting.openai_api_key:
                    api_key = encryption.decrypt(setting.openai_api_key)
                    db.close()
                    return OpenAILLMClient(api_key)
        
        db.close()
    except Exception as e:
        print(f"Error fetching LLM settings from database: {e}")
    
    # Fall back to environment variable for OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAILLMClient(api_key)
    
    return MockLLMClient()
