from abc import ABC, abstractmethod
import os
# import openai # Uncomment when ready

import json
from openai import OpenAI
from backend.analysis.categories import FailureCategory, Severity

# Build category list for prompt
CATEGORY_LIST = "\n".join([f"- {c.value}" for c in FailureCategory])

SYSTEM_PROMPT = f"""You are an Expert Android System Engineer specializing in GMS (Google Mobile Services) Certification.
Your task is to analyze a single test failure and classify it precisely.

Output a strict JSON object with these keys:
- 'root_cause': Technical hypothesis (e.g., "Buffer overflow in audio HAL", "Race condition in UI").
- 'solution': Actionable fix (e.g., "Increase buffer size", "Add synchronization").
- 'ai_summary': A concise one-sentence title for this failure.
- 'severity': One of ["Critical", "High", "Medium", "Low"].
- 'category': Exact classification from this list:
{CATEGORY_LIST}
- 'confidence_score': 1-5 (5=Highest).
- 'suggested_assignment': The most appropriate team (e.g., "Audio Team", "System UI", "Kernel").
"""

SUBMISSION_SYSTEM_PROMPT = f"""You are a Senior Android System Engineer at a chipset vendor (like Qualcomm/MediaTek). You are reviewing a consolidated GMS test report for a Tech Lead.
Your goal is to "Triage" the critical failures to help the Tech Lead decide: "Is this a BSP bug, an AOSP bug, or an Infra issue?"

Analyze the provided list of PERSISTENT failures (transient failures have already been filtered out).
Use the following standardized Categories for classification:
{CATEGORY_LIST}

Return a strict JSON response with the following keys:
- 'executive_summary': A 2-sentence technical summary. Focus on ROOT CAUSE hypothesis (e.g., "High number of MediaCodec failures suggests potential ION memory leak or DSP driver regression.").
- 'top_risks': A list of strings (max 3) highlighting the top blockers. Be specific (e.g., "CtsMediaTestCases - potential Decoder hang").
- 'recommendations': A list of actionable steps (max 3). Assign to teams: Audio, Display, Kernel, Infra. (e.g., "[Kernel] Check dmesg for OOM killer", "[Infra] Verify wifi stability").
- 'severity_score': Integer 0-100. (0=Clean, 100=Unreleasable).
    - >80: Critical BSP crash/hang.
    - 50-80: Functional regression in major modules.
    - <20: Minor flakes or known waivers.
- 'analyzed_clusters': A list of objects for each major failure pattern found. Each object must have:
    - 'pattern_name': Short name (e.g., "MediaCodec Timeout").
    - 'count': Integer (number of occurrences).
    - 'root_cause': Technical hypothesis (e.g., "DSP failed to release buffer").
    - 'solution': Suggested fix (e.g., "Check ION heap size").
    - 'redmine_component': Suggested Redmine Project/Component (e.g., "BSP - Multimedia").
    - 'category': The category from the standard list above.
"""

class LLMClient(ABC):
    @abstractmethod
    def analyze_failure(self, failure_text: str) -> dict:
        pass

    @abstractmethod
    def analyze_submission(self, failures_text: str) -> dict:
        """Analyze a collection of failures for a full submission report."""
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
    
    def analyze_submission(self, failures_text: str) -> dict:
        return {
            "executive_summary": "Mock Analysis: Several stability issues detected in this build, primarily affecting media playback and keymaster.",
            "top_risks": ["Media Codec Timeout", "Keymaster TEE Failure"],
            "recommendations": ["Investigate DSP load during media playback", "Check TrustZone logs for keymaster errors"],
            "severity_score": 65
        }

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
            
            # Combine title and summary for backward compatibility
            if 'title' in result and 'summary' in result:
                result['ai_summary'] = f"{result['title']}\n{result['summary']}"
            elif 'title' in result:
                 result['ai_summary'] = result['title']
            elif 'summary' in result:
                 result['ai_summary'] = result['summary']
                 
            return result
        except Exception as e:
            print(f"OpenAI API call failed: {e}")
            return self._get_error_response(e)

    def analyze_submission(self, failures_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SUBMISSION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze these failures from a GMS submission:\n\n{failures_text[:10000]}"}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
             print(f"OpenAI Submission Analysis failed: {e}")
             return self._get_submission_error_response(e)

    def _get_error_response(self, e):
         return {
            "root_cause": "AI Analysis Failed",
            "solution": f"Error: {str(e)}",
            "ai_summary": "Analysis failed due to API error.",
            "severity": "Low",
            "category": "Unknown",
            "confidence_score": 1,
            "suggested_assignment": "Unknown"
        }
        
    def _get_submission_error_response(self, e):
         return {
            "executive_summary": f"AI Analysis Failed: {str(e)}",
            "top_risks": ["Analysis Error"],
            "recommendations": ["Check API Configuration"],
            "severity_score": 0
        }


class InternalLLMClient(LLMClient):
    """LLM client for internal Ollama/vLLM servers with OpenAI-compatible API."""
    
    def __init__(self, base_url: str, model: str = "llama3.1:8b", api_key: str = "not-needed"):
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
            
            if 'title' in result and 'summary' in result:
                result['ai_summary'] = f"{result['title']}\n{result['summary']}"
            elif 'title' in result:
                 result['ai_summary'] = result['title']
            elif 'summary' in result:
                 result['ai_summary'] = result['summary']
                 
            return result
        except Exception as e:
            print(f"Internal LLM API call failed ({self.base_url}): {e}")
            return self._get_error_response(e)

    def analyze_submission(self, failures_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUBMISSION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze these failures from a GMS submission:\n\n{failures_text[:5000]}"}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
             print(f"Internal LLM Submission Analysis failed: {e}")
             return self._get_submission_error_response(e)

    def _get_error_response(self, e):
         return {
            "root_cause": "AI Analysis Failed",
            "solution": f"Error connecting to internal LLM: {str(e)}",
            "ai_summary": "Analysis failed due to internal LLM error.",
            "severity": "Low",
            "category": "Unknown",
            "confidence_score": 1,
            "suggested_assignment": "Unknown"
        }

    def _get_submission_error_response(self, e):
         return {
            "executive_summary": f"AI Analysis Failed: {str(e)}",
            "top_risks": ["Internal API Error"],
            "recommendations": ["Check Internal LLM Service"],
            "severity_score": 0
        }


class CambrianLLMClient(LLMClient):
    """LLM client for Cambrian internal gateway with SSL verification disabled."""
    
    def __init__(self, base_url: str, api_key: str, model: str = "LLAMA 3.3 70B"):
        import httpx
        http_client = httpx.Client(verify=False)
        
        if base_url and not base_url.endswith('/v1'):
            if base_url.endswith('/'):
                base_url = f"{base_url}v1"
            else:
                base_url = f"{base_url}/v1"
                
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
            
            if 'title' in result and 'summary' in result:
                result['ai_summary'] = f"{result['title']}\n{result['summary']}"
            elif 'title' in result:
                 result['ai_summary'] = result['title']
            elif 'summary' in result:
                 result['ai_summary'] = result['summary']
                 
            return result
        except Exception as e:
            print(f"Cambrian LLM API call failed ({self.base_url}): {e}")
            return self._get_error_response(e)

    def analyze_submission(self, failures_text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUBMISSION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze these failures from a GMS submission:\n\n{failures_text[:10000]}"}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
             print(f"Cambrian LLM Submission Analysis failed: {e}")
             return self._get_submission_error_response(e)

    def _get_error_response(self, e):
         return {
            "root_cause": "AI Analysis Failed",
            "solution": f"Error connecting to Cambrian: {str(e)}",
            "ai_summary": "Analysis failed due to Cambrian API error.",
            "severity": "Low",
            "category": "Unknown",
            "confidence_score": 1,
            "suggested_assignment": "Unknown"
        }
        
    def _get_submission_error_response(self, e):
         return {
            "executive_summary": f"AI Analysis Failed: {str(e)}",
            "top_risks": ["Cambrian API Error"],
            "recommendations": ["Check Cambrian Token"],
            "severity_score": 0
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
