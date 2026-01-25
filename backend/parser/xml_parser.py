from backend.parser.base_parser import BaseParser
from lxml import etree
from typing import Generator, Dict, Any
import os

class XMLParser(BaseParser):
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        context = etree.iterparse(file_path, events=('start',))
        metadata = {
            "test_suite_name": "Unknown",
            "device_fingerprint": "Unknown",
            "build_id": "Unknown",
            "build_product": "Unknown",
            "build_model": "Unknown",
            "build_type": "Unknown",
            "security_patch": "Unknown",
            "android_version": "Unknown",
            "suite_version": "Unknown",
            "suite_plan": "Unknown",
            "suite_build_number": "Unknown",
            "host_name": "Unknown",
            "start_time": None,
            "end_time": None,
            "modules_done": 0,
            "modules_total": 0
        }
        
        try:
            for event, elem in context:
                # Use endswith to handle namespaces (e.g. {http://...}Result)
                if elem.tag.endswith('Result'):
                    metadata["test_suite_name"] = elem.get('suite_name', 'Unknown')
                    metadata["start_time"] = elem.get('start')
                    metadata["end_time"] = elem.get('end')
                    metadata["start_display"] = elem.get('start_display')
                    metadata["end_display"] = elem.get('end_display')
                    metadata["host_name"] = elem.get('host_name', 'Unknown')
                    metadata["suite_version"] = elem.get('suite_version', 'Unknown')
                    metadata["suite_plan"] = elem.get('suite_plan', 'Unknown')
                    metadata["suite_build_number"] = elem.get('suite_build_number', 'Unknown')
                elif elem.tag.endswith('Build'):
                    metadata["device_fingerprint"] = elem.get('build_fingerprint', 'Unknown') # Note: XML uses build_fingerprint usually, checking sample
                    # Re-checking sample_cts.xml for attribute names
                    # sample_cts.xml: <Build ... build_fingerprint="..." build_id="..." build_product="..." ... />
                    # Wait, line 3 says: build_fingerprint="Trimble/T70/thorpe:15/..."
                    # The original code used elem.get('fingerprint', 'Unknown'). 
                    # Let's check if 'fingerprint' exists or if it should be 'build_fingerprint'.
                    # Looking at sample_cts.xml line 3: build_fingerprint="..."
                    # So original code might be wrong or generic. I will use build_fingerprint.
                    if metadata["device_fingerprint"] == 'Unknown':
                         metadata["device_fingerprint"] = elem.get('build_fingerprint', 'Unknown')
                    
                    metadata["build_id"] = elem.get('build_id', 'Unknown')
                    metadata["build_product"] = elem.get('build_product', 'Unknown')
                    metadata["build_model"] = elem.get('build_model', 'Unknown')
                    metadata["build_type"] = elem.get('build_type', 'Unknown')
                    metadata["security_patch"] = elem.get('build_version_security_patch', 'Unknown')
                    metadata["android_version"] = elem.get('build_version_release', 'Unknown')
                    metadata["build_version_sdk"] = elem.get('build_version_sdk', 'Unknown')
                    metadata["build_version_incremental"] = elem.get('build_version_incremental', 'Unknown')
                elif elem.tag.endswith('Summary'):
                    try:
                        metadata["modules_done"] = int(elem.get('modules_done', 0))
                        metadata["modules_total"] = int(elem.get('modules_total', 0))
                    except (ValueError, TypeError):
                        pass
                
                # We only need the top-level info, so we can stop early if we have everything
                # Summary comes after Build, so check for it too
                if (metadata["test_suite_name"] != "Unknown" and 
                    metadata["device_fingerprint"] != "Unknown" and
                    metadata["modules_total"] > 0):
                    break
                
                # Clear element to save memory
                elem.clear()
        except Exception as e:
            print(f"Error parsing metadata: {e}")
            
        del context
        return metadata

    def parse(self, file_path: str) -> Generator[Dict[str, Any], None, None]:
        # CTS/VTS XML structure usually:
        # <Result>
        #   <Module name="...">
        #     <TestCase name="...">
        #       <Test name="..." result="...">
        #         <Failure message="..." stack="..." />
        #       </Test>
        #     </TestCase>
        #   </Module>
        # </Result>

        context = etree.iterparse(file_path, events=('end',))
        
        current_module = None
        current_class = None

        for event, elem in context:
            if elem.tag.endswith('Module'):
                # Handle Module (End event)
                current_module = elem.get('name')
                
                yield {
                    "type": "module_info",
                    "module_name": elem.get('name'),
                    "module_abi": elem.get('abi')
                }
                pass
            
            elif elem.tag.endswith('Test'):
                # This is a test case result
                # This is a test case result
                test_name = elem.get('name')
                result_status = elem.get('result')
                
                # Get parent info
                test_case_elem = elem.getparent()
                class_name = test_case_elem.get('name') if test_case_elem is not None else "Unknown"
                
                module_elem = test_case_elem.getparent() if test_case_elem is not None else None
                module_name = module_elem.get('name') or module_elem.get('appPackageName') if module_elem is not None else "Unknown"
                module_abi = module_elem.get('abi') or module_elem.get('digests') if module_elem is not None else "Unknown"
                
                # Extract failure info if any
                failure_msg = None
                stack_trace = None
                
                # Find Failure child
                # Since we are at 'end' of Test, children are processed. 
                # Find Failure/TestResult elements in the current Test element
                if not result_status:
                    # Find Failure/TestResult elements in the current Test element
                    pass # logic moved to loop below

                # Find Failure/TestResult elements in the current Test element
                for child in elem:
                    if child.tag.endswith('Failure'):
                        failure_msg = child.get('message')
                        # Stacktrace is text of child or child's child
                        stack_trace = child.text
                        for sub in child:
                            if sub.tag.endswith('StackTrace'):
                                stack_trace = sub.text
                    elif child.tag.endswith('TestResult'):
                         if not result_status: result_status = child.get('result') # Fallback result

                # Only yield if we found a module context (or at least a test name)
                if test_name: 
                     yield {
                        "module_name": module_name,
                        "module_abi": module_abi,
                        "class_name": class_name,
                        "method_name": test_name,
                        "status": result_status,
                        "stack_trace": stack_trace,
                        "error_message": failure_msg
                    }
                
                # Important: clear the element to save memory
                elem.clear()
                # Also clear predecessors to keep memory low
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
            
                
        del context
