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
            if elem.tag == 'Module':
                current_module = elem.get('name')
                # It's an end event, so we are done with this module. 
                # Actually for iterparse 'end', we get the element when it's fully parsed.
                # But we need the context *during* the children parsing.
                # So we might need to track hierarchy differently or just use the fact that
                # we are processing leaf nodes (Test) and they should have parent info?
                # No, lxml iterparse 'end' means the element is complete.
                # So when we are at 'Test', its parent 'TestCase' is NOT yet complete (end event hasn't fired).
                # But we can access elem.getparent()!
                pass
            
            elif elem.tag == 'Test':
                # This is a test case result
                test_name = elem.get('name')
                result_status = elem.get('result')
                
                # Get parent info
                test_case_elem = elem.getparent()
                class_name = test_case_elem.get('name') if test_case_elem is not None else "Unknown"
                
                module_elem = test_case_elem.getparent() if test_case_elem is not None else None
                module_name = module_elem.get('name') if module_elem is not None else "Unknown"
                module_abi = module_elem.get('abi') if module_elem is not None else "Unknown"
                
                # Extract failure info if any
                failure_elem = elem.find('Failure')
                stack_trace = None
                error_message = None
                
                if failure_elem is not None:
                    error_message = failure_elem.get('message')
                    
                    # Try to get stack trace from multiple possible locations
                    # 1. Check for <StackTrace> child element
                    stack_elem = failure_elem.find('StackTrace')
                    if stack_elem is not None and stack_elem.text:
                        stack_trace = stack_elem.text.strip()
                    
                    # 2. Fallback to 'stack' attribute
                    if not stack_trace:
                        stack_trace = failure_elem.get('stack')
                    
                    # 3. Fallback to text content of Failure element itself
                    if not stack_trace:
                        stack_trace = failure_elem.text

                yield {
                    "module_name": module_name,
                    "module_abi": module_abi,
                    "class_name": class_name,
                    "method_name": test_name,
                    "status": result_status,
                    "stack_trace": stack_trace,
                    "error_message": error_message
                }
                
                # Important: clear the element to save memory
                elem.clear()
                # Also clear predecessors to keep memory low
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
            
            elif elem.tag == 'Module':
                # Clear module after we are done with it
                elem.clear()
                
        del context
