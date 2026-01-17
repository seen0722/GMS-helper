import sys
import os
import xml.etree.ElementTree as ET

# Add root to sys.path
sys.path.append(os.getcwd())

def test_parsing():
    file_path = "!sample_cts.xml"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found")
        return

    print(f"Parsing {file_path}...")
    context = ET.iterparse(file_path, events=('start',))
    
    metadata = {
        "test_suite_name": "Unknown",
        "start_time": None,
        "end_time": None,
        "device_fingerprint": "Unknown"
    }

    try:
        count = 0
        for event, elem in context:
            count += 1
            # print(f"Tag: {elem.tag}, Attributes: {elem.keys()}")
            
            if elem.tag == 'Result':
                metadata["test_suite_name"] = elem.get('suite_name', 'Unknown')
                metadata["start_time"] = elem.get('start')
                metadata["end_time"] = elem.get('end')
                metadata["start_display"] = elem.get('start_display')
                metadata["end_display"] = elem.get('end_display')
                print(f"Found 'Result': start={metadata['start_time']}")
                print(f"Found 'Result': start_display={metadata['start_display']}")
                
            elif elem.tag == 'Build':
                metadata["device_fingerprint"] = elem.get('build_fingerprint', 'Unknown')
                metadata["build_version_incremental"] = elem.get('build_version_incremental', 'Unknown')
                print(f"Found 'Build': fingerprint={metadata['device_fingerprint']}")
                print(f"Found 'Build': incremental={metadata['build_version_incremental']}")
            
            if metadata["test_suite_name"] != "Unknown" and metadata["device_fingerprint"] != "Unknown":
                print("Breaking early (metadata found)")
                break

    except Exception as e:
        print(f"Error: {e}")

    print("Parsed Metadata:")
    for k, v in metadata.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    test_parsing()
