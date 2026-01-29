
from backend.parser.xml_parser import XMLParser
import os

# Pick a recent file (or passed as arg)
UPLOAD_DIR = "/Users/chenzeming/dev/GMS-helper/uploads"
# Pick a small file
TEST_FILE = os.path.join(UPLOAD_DIR, "013dd3db-1d81-4970-a5a3-4ba55d693bc2_sample_cts.xml") 

if not os.path.exists(TEST_FILE):
    # Fallback to finding one
    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".xml")]
    if files:
        TEST_FILE = os.path.join(UPLOAD_DIR, files[-1])
        print(f"Using found file: {TEST_FILE}")

print(f"Testing Parser on: {TEST_FILE}")

parser = XMLParser()
module_count = 0
test_count = 0

for item in parser.parse(TEST_FILE):
    if item.get("type") == "module_info":
        module_count += 1
        print(f"Found Module: {item['module_name']} (ABI: {item['module_abi']})")
    else:
        test_count += 1

print(f"Total Modules Found: {module_count}")
print(f"Total Tests Found: {test_count}")
