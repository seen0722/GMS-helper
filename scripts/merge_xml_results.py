import xml.etree.ElementTree as ET
import argparse
import sys
import os

def parse_xml(file_path):
    try:
        tree = ET.parse(file_path)
        return tree
    except ET.ParseError as e:
        print(f"Error parsing {file_path}: {e}")
        sys.exit(1)

def get_module_key(module_element):
    """Returns a unique key for a module based on name and abi."""
    return (module_element.get('name'), module_element.get('abi'))

def merge_xmls(base_path, patch_path, output_path):
    print(f"Loading Base XML: {base_path}")
    base_tree = parse_xml(base_path)
    base_root = base_tree.getroot()

    print(f"Loading Patch XML: {patch_path}")
    patch_tree = parse_xml(patch_path)
    patch_root = patch_tree.getroot()

    # limit to 'Module' tags
    # Index base modules
    base_modules = {}
    for module in base_root.findall('Module'):
        key = get_module_key(module)
        base_modules[key] = module

    # Process patch modules
    patched_count = 0
    new_count = 0
    
    for patch_module in patch_root.findall('Module'):
        key = get_module_key(patch_module)
        
        if key in base_modules:
            # Replace existing module
            # We need to find the index to replace it in place to preserve order if possible, 
            # or just remove old and append new if order doesn't matter strictly (usually it doesn't for tools, but nice for humans)
            # Efficient way in ElementTree is tricky for in-place replacement by key without parent ref.
            # So we will do a second pass to construct the new list or remove from parent.
            
            # Strategy: valid base modules are modified directly or lazily.
            # Actually, ElementTree elements can be removed.
            
            # Let's find the specific object in the list and remove it.
            # But 'findall' returns a list copy.
            # We need to iterate the children of root.
            pass
        else:
            # This is a new module not in base? Unlikely for retry, but possible if filters changed.
            pass

    # Better approach: List reconstruction with Deep Merge
    patch_map = {get_module_key(m): m for m in patch_root.findall('Module')}
    
    headers = [c for c in base_root if c.tag != 'Module']
    base_modules_list = [c for c in base_root if c.tag == 'Module']
    
    # Clear root
    for c in list(base_root):
        base_root.remove(c)
        
    # Re-add headers
    for h in headers:
        base_root.append(h)
        
    # Re-add modules (merged)
    added_keys = set()
    
    for module in base_modules_list:
        key = get_module_key(module)
        if key in patch_map:
            # Overlap found: Perform Deep Merge (Optimistic)
            print(f"  Merging module: {key}")
            merged_module = merge_module_optimistic(module, patch_map[key])
            base_root.append(merged_module)
            added_keys.add(key)
            patched_count += 1
        else:
            # Keep base
            base_root.append(module)
            
    # Add any remaining patch modules that weren't in base
    for key, module in patch_map.items():
        if key not in added_keys:
            print(f"  Adding new {key} from 2nd file")
            base_root.append(module)
            added_keys.add(key)
            new_count += 1

    print(f"Merged: {patched_count} modules merged, {new_count} new modules added.")

    # Update Summary
    total_pass = 0
    total_fail = 0
    modules_done = 0
    modules_total = 0
    
    for module in base_root.findall('Module'):
        modules_total += 1
        if module.get('done') == 'true':
            modules_done += 1
        
        # Count tests inside
        current_pass = 0
        current_fail = 0
        for testcase in module.findall('TestCase'):
            for test in testcase.findall('Test'):
                res = test.get('result')
                if res == 'pass':
                    current_pass += 1
                    total_pass += 1
                elif res == 'fail':
                    current_fail += 1
                    total_fail += 1
        
        # Update Module-level stats if needed (optional but good for consistency)
        # Note: 'total_tests' usually includes ignored? Let's just update pass/fail/total
        # CTS XML usually has 'pass', 'failed' attributes on Module too?
        if module.get('pass'):
            module.set('pass', str(current_pass))
            # Some XMLs don't have 'failed' attribute on Module, but if they do:
            # module.set('failed', str(current_fail)) 
            # Check if source had it. `base_root` elements are reference.
    
    print(f"Recalculated Summary: Pass={total_pass}, Fail={total_fail}, Done={modules_done}/{modules_total}")
    
    summary_elem = base_root.find('Summary')
    if summary_elem is not None:
        summary_elem.set('pass', str(total_pass))
        summary_elem.set('failed', str(total_fail))
        summary_elem.set('modules_done', str(modules_done))
        summary_elem.set('modules_total', str(modules_total))
    else:
        s = ET.Element('Summary')
        s.set('pass', str(total_pass))
        s.set('failed', str(total_fail))
        s.set('modules_done', str(modules_done))
        s.set('modules_total', str(modules_total))
        base_root.insert(0, s)

    # Write output
    base_tree.write(output_path, encoding='UTF-8', xml_declaration=True)
    print(f"Saved merged XML to {output_path}")

def merge_module_optimistic(base_module, patch_module):
    """
    Merges patch_module into base_module with Optimistic logic:
    - Any Pass is a Pass.
    - If Base=Pass, Patch=Fail -> Result=Pass (Reference Base)
    - If Base=Fail, Patch=Pass -> Result=Pass (Reference Patch)
    - If Base=Fail, Patch=Fail -> Result=Fail (Reference Patch usually better for logs)
    """
    # Map Base TestCases
    # Structure: TestCase -> Test
    # Key: (TestCase Name, Test Name)
    
    base_tests = {}
    for tc in base_module.findall('TestCase'):
        tc_name = tc.get('name')
        for t in tc.findall('Test'):
            t_name = t.get('name')
            base_tests[(tc_name, t_name)] = t

    patch_tests = {}
    patch_testcases_map = {} # To find parent TestCase element easily
    
    for tc in patch_module.findall('TestCase'):
        tc_name = tc.get('name')
        patch_testcases_map[tc_name] = tc
        for t in tc.findall('Test'):
            t_name = t.get('name')
            patch_tests[(tc_name, t_name)] = t
            
    # We will build a NEW list of children for the base_module (or modifying it in place)
    # Strategy: Start with Patch Module structure (usually newer), but check Base for "better" results.
    # actually, Base module might have MORE tests (if patch was partial).
    # So we should start with union of keys.
    
    # But XML structure is hierarchical.
    # Let's clean base_module children and rebuild.
    
    # 1. Collect all unique TestCase names
    # 2. For each TestCase, collect all unique Test names
    
    all_tc_names = set()
    for tc in base_module.findall('TestCase'): all_tc_names.add(tc.get('name'))
    for tc in patch_module.findall('TestCase'): all_tc_names.add(tc.get('name'))
    
    # Clear base module children (TestCases)
    # Be careful not to verify other children? (usually just TestCase)
    for child in list(base_module):
        base_module.remove(child)
        
    for tc_name in sorted(all_tc_names):
        # Create new TestCase element
        new_tc = ET.Element('TestCase')
        new_tc.set('name', tc_name)
        
        # Find all tests for this class
        # (This implies re-scanning or we should have pre-grouped. Pre-grouping is better)
        # Optimization: Map TC_Name -> Set(TestNames)
        pass # implemented implicitly below
        
        # Build list of tests for this TC
        # We need to find the source TestCases again or look into our flat map with filtering (slow)
        # Let's reuse the Element objects but be careful about parenting.
        
        # Helper to find tests in a module for a specific TC
        # (Refactoring: Pre-parse everything into a dict structure would be cleaner)
        pass

    # Re-Implementation: In-place Update of Base
    # Iterate Patch Tests. Update Base if Patch is better or Base is missing.
    # But wait, we want "Any Pass".
    # Base=Pass, Patch=Fail -> Keep Base.
    # Base=Fail, Patch=Pass -> Update to Patch.
    
    # AND we need to add NEW tests from Patch that aren't in Base.
    
    # 1. Map Base Structure: Dict[tc_name] -> Dict[t_name] -> Element
    base_structure = {}
    for tc in base_tests.keys():
        tc_n, t_n = tc
        if tc_n not in base_structure: base_structure[tc_n] = {}
        base_structure[tc_n][t_n] = base_tests[tc]
        
    # 2. Iterate Patch
    # If test exists in Base:
    #   if Patch=Pass and Base!=Pass: Replace Base Element with Patch Element (Update)
    #   if Patch=Fail and Base=Pass: Do NOTHING (Optimistic - Keep Base)
    #   if Patch=Fail and Base!=Pass: Replace Base Element (Update logs)
    # If test NOT in Base:
    #   Add to Base Structure
    
    # Problem: Adding to Base Structure requires "TestCase" parent.
    # If TestCase parent doesn't exist in Base, we need to create it.
    
    # Let's perform the updates on a Data Structure and then serialize back to XML elements?
    # Or just manipulate the XML tree directly.
    
    # We need to easily find TestCase elements in Base Module to append new Tests.
    base_tc_elements = {tc.get('name'): tc for tc in base_module.findall('TestCase')} # Old children were removed? No, I delayed that.
    
    # Re-reading base module children since I removed them in previous code block draft?
    # Wait, the code above `for child in list(base_module): base_module.remove(child)` REPLACES the implementation.
    # So I need to implement the FULL logic here.
    
    # Let's use the 'base_module' passed in as the container to return. 
    # But I want to KEEP valid Base children.
    
    # Map existing Base TestCases
    base_tc_map = {tc.get('name'): tc for tc in base_module.findall('TestCase')}
    
    for tc_name, patch_tc in patch_testcases_map.items():
        if tc_name not in base_tc_map:
            # Entirely new TestCase in Patch -> Add it
            # Deep copy recommended? ET elements are mutable.
            # Append clone/ref
            base_module.append(patch_tc) 
            continue
            
        # TestCase exists in both. Merge Tests.
        base_tc = base_tc_map[tc_name]
        
        # Map Base Tests
        base_test_map = {t.get('name'): t for t in base_tc.findall('Test')}
        
        for patch_t in patch_tc.findall('Test'):
            t_name = patch_t.get('name')
            p_res = patch_t.get('result')
            
            if t_name in base_test_map:
                base_t = base_test_map[t_name]
                b_res = base_t.get('result')
                
                # OPTIMISTIC LOGIC
                if b_res == 'pass':
                    # Base Passed. KEEPER. Even if Patch Failed.
                    continue 
                
                if p_res == 'pass':
                    # Patch Passed. Update Base to match Patch.
                    # Replace element content
                    replace_element_content(base_t, patch_t)
                else:
                    # Both Failed (or Base=Fail, Patch=Fail).
                    # Usually prefer Patch (Newer logs).
                    replace_element_content(base_t, patch_t)
            else:
                # Test new in Patch -> Add to Base TC
                base_tc.append(patch_t)
                
    return base_module

def replace_element_content(target, source):
    """Replaces attributes and children of target with source."""
    target.clear()
    target.tag = source.tag
    target.attrib = source.attrib
    for child in source:
        target.append(child)
    if source.text:
        target.text = source.text
    if source.tail:
        target.tail = source.tail

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge two CTS/GTS XML result files.")
    parser.add_argument("--base", required=True, help="Path to the base XML file (full run)")
    parser.add_argument("--patch", required=True, help="Path to the patch XML file (retry run)")
    parser.add_argument("--output", required=True, help="Output path for merged XML")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.base):
        print(f"Base file not found: {args.base}")
        sys.exit(1)
    if not os.path.exists(args.patch):
        print(f"Patch file not found: {args.patch}")
        sys.exit(1)
        
    merge_xmls(args.base, args.patch, args.output)
