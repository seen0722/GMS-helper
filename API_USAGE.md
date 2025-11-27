# API Usage Guide - Upload XML Test Results

This guide shows how to upload test result XML files using the API endpoint directly.

## 📡 Upload Endpoint

```
POST /api/upload/
```

**Content-Type**: `multipart/form-data`

---

## 🔧 Using cURL

### Basic Upload
```bash
curl -X POST \
  -F "file=@/path/to/test_result.xml" \
  http://localhost:8000/api/upload/
```

### Upload to Remote Server
```bash
curl -X POST \
  -F "file=@sample_cts.xml" \
  https://gms.zmlab.io/api/upload/
```

### With Progress Bar
```bash
curl -X POST \
  -F "file=@test_result.xml" \
  --progress-bar \
  http://localhost:8000/api/upload/ | cat
```

### Example Response (Success)
```json
{
  "message": "File uploaded. Processing started in background.",
  "test_run_id": 5,
  "status": "pending"
}
```

---

## 🐍 Using Python

### Simple Upload
```python
import requests

url = "http://localhost:8000/api/upload/"
file_path = "sample_cts.xml"

with open(file_path, 'rb') as f:
    files = {'file': f}
    response = requests.post(url, files=files)
    
print(response.json())
# Output: {'message': '...', 'test_run_id': 5, 'status': 'pending'}
```

### Upload with Progress
```python
import requests
from tqdm import tqdm

def upload_with_progress(file_path, url):
    """Upload file with progress bar"""
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        with tqdm(total=file_size, unit='B', unit_scale=True, desc='Uploading') as pbar:
            def callback(monitor):
                pbar.update(monitor.bytes_read - pbar.n)
            
            files = {'file': f}
            response = requests.post(url, files=files)
    
    return response.json()

# Usage
result = upload_with_progress('test_result.xml', 'http://localhost:8000/api/upload/')
print(f"Test Run ID: {result['test_run_id']}")
```

### Complete Example with Error Handling
```python
import requests
import sys
import time

def upload_test_result(file_path, server_url="http://localhost:8000"):
    """
    Upload test result XML and wait for processing
    
    Args:
        file_path: Path to XML file
        server_url: Base URL of the server
    
    Returns:
        dict: Test run information
    """
    upload_url = f"{server_url}/api/upload/"
    
    print(f"📤 Uploading {file_path}...")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path, f, 'application/xml')}
            response = requests.post(upload_url, files=files, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            test_run_id = result['test_run_id']
            print(f"✅ Upload successful! Test Run ID: {test_run_id}")
            
            # Wait for processing
            print("⏳ Processing test results...")
            time.sleep(2)
            
            # Get run details
            run_url = f"{server_url}/api/reports/runs/{test_run_id}"
            run_response = requests.get(run_url)
            
            if run_response.status_code == 200:
                run_data = run_response.json()
                print(f"📊 Test Suite: {run_data['test_suite_name']}")
                print(f"📊 Total Tests: {run_data['total_tests']}")
                print(f"✅ Passed: {run_data['passed']}")
                print(f"❌ Failed: {run_data['failed']}")
                print(f"🔗 View at: {server_url}/?page=run-details&id={test_run_id}")
                return run_data
            else:
                print(f"⚠️  Could not fetch run details")
                return result
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Error: {response.text}")
            return None
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Upload timeout (file too large or slow connection)")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

# Usage
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload.py <xml_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    upload_test_result(file_path)
```

**Save as `upload.py` and run:**
```bash
python upload.py sample_cts.xml
```

---

## 🌐 Using JavaScript/Node.js

### Using Fetch API (Browser)
```javascript
async function uploadTestResult(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload/', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Upload successful!', result);
            return result;
        } else {
            throw new Error('Upload failed');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Usage with file input
document.getElementById('fileInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    uploadTestResult(file);
});
```

### Using Node.js with FormData
```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function uploadTestResult(filePath) {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    
    try {
        const response = await axios.post(
            'http://localhost:8000/api/upload/',
            form,
            {
                headers: form.getHeaders(),
                maxContentLength: Infinity,
                maxBodyLength: Infinity
            }
        );
        
        console.log('Upload successful!', response.data);
        return response.data;
    } catch (error) {
        console.error('Upload failed:', error.message);
    }
}

// Usage
uploadTestResult('./sample_cts.xml');
```

---

## 🔄 CI/CD Integration Examples

### GitHub Actions
```yaml
name: Upload Test Results

on:
  push:
    paths:
      - 'test_results/*.xml'

jobs:
  upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Upload to GMS Analyzer
        run: |
          curl -X POST \
            -F "file=@test_results/cts_result.xml" \
            ${{ secrets.GMS_ANALYZER_URL }}/api/upload/
```

### Jenkins Pipeline
```groovy
pipeline {
    agent any
    
    stages {
        stage('Upload Test Results') {
            steps {
                script {
                    sh '''
                        curl -X POST \
                          -F "file=@${WORKSPACE}/test_result.xml" \
                          ${GMS_ANALYZER_URL}/api/upload/
                    '''
                }
            }
        }
    }
}
```

### GitLab CI
```yaml
upload_results:
  stage: test
  script:
    - |
      curl -X POST \
        -F "file=@test_results.xml" \
        ${GMS_ANALYZER_URL}/api/upload/
  only:
    - main
```

---

## 📊 Check Upload Status

After uploading, you can check the processing status:

### Get Run Details
```bash
# Get the test_run_id from upload response
TEST_RUN_ID=5

# Get run details
curl http://localhost:8000/api/reports/runs/${TEST_RUN_ID}
```

### Response Example
```json
{
  "id": 5,
  "test_suite_name": "CTS",
  "total_tests": 1500,
  "passed": 1450,
  "failed": 50,
  "skipped": 0,
  "build_fingerprint": "google/sdk_gphone64_arm64/...",
  "device_fingerprint": "google/sdk_gphone64_arm64/...",
  "build_id": "TP1A.220624.014",
  "build_product": "sdk_gphone64_arm64",
  "build_model": "sdk_gphone64_arm64",
  "android_version": "13",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 🔍 Advanced: Batch Upload Script

Upload multiple XML files:

```python
#!/usr/bin/env python3
"""
Batch upload test results to GMS Analyzer
"""
import os
import sys
import requests
from pathlib import Path

def batch_upload(directory, server_url="http://localhost:8000"):
    """Upload all XML files in a directory"""
    xml_files = list(Path(directory).glob("*.xml"))
    
    if not xml_files:
        print(f"No XML files found in {directory}")
        return
    
    print(f"Found {len(xml_files)} XML files")
    results = []
    
    for xml_file in xml_files:
        print(f"\n📤 Uploading {xml_file.name}...")
        
        try:
            with open(xml_file, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{server_url}/api/upload/",
                    files=files,
                    timeout=300
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success! Test Run ID: {result['test_run_id']}")
                results.append({
                    'file': xml_file.name,
                    'test_run_id': result['test_run_id'],
                    'status': 'success'
                })
            else:
                print(f"❌ Failed: {response.status_code}")
                results.append({
                    'file': xml_file.name,
                    'status': 'failed',
                    'error': response.text
                })
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            results.append({
                'file': xml_file.name,
                'status': 'error',
                'error': str(e)
            })
    
    # Summary
    print("\n" + "="*50)
    print("📊 Upload Summary")
    print("="*50)
    successful = sum(1 for r in results if r['status'] == 'success')
    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {len(results) - successful}/{len(results)}")
    
    for result in results:
        if result['status'] == 'success':
            print(f"  ✅ {result['file']} → Run ID: {result['test_run_id']}")
        else:
            print(f"  ❌ {result['file']} → {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_upload.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    batch_upload(directory)
```

**Usage:**
```bash
python batch_upload.py ./test_results/
```

---

## 🛡️ Error Handling

### Common Errors

| Status Code | Error | Solution |
|-------------|-------|----------|
| 400 | Invalid file format | Ensure file is valid XML |
| 413 | File too large | Check nginx `client_max_body_size` |
| 500 | Server error | Check server logs |
| 504 | Gateway timeout | Increase timeout settings |

### Check Server Logs
```bash
# Application logs
sudo tail -f /var/log/gms-analyzer.out.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

---

## 📝 API Reference Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload/` | POST | Upload test result XML |
| `/api/reports/runs` | GET | List all test runs |
| `/api/reports/runs/{id}` | GET | Get run details |
| `/api/reports/runs/{id}/stats` | GET | Get run statistics |
| `/api/reports/runs/{id}/failures` | GET | Get failure list |
| `/api/analysis/run/{id}` | POST | Start AI analysis |
| `/api/analysis/run/{id}/status` | GET | Check analysis status |
| `/api/analysis/run/{id}/clusters` | GET | Get failure clusters |

---

## 💡 Tips

1. **Large Files**: For files >100MB, ensure:
   - Nginx: `client_max_body_size 1000M;`
   - Timeout: `proxy_read_timeout 600;`
   - Use DNS-only mode in Cloudflare (no proxy)

2. **Automation**: Save the `test_run_id` from upload response for later analysis

3. **Monitoring**: Check upload status via `/api/reports/runs/{id}`

4. **Security**: In production, add authentication to the API

---

Need help with a specific use case? Let me know! 🚀
