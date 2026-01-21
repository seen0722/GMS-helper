/**
 * XML Parser Web Worker
 * Streaming parse CTS/VTS XML results, extracting metadata, stats, and failures only.
 * Uses pure JS SAX-style parsing for memory efficiency.
 */

// Simple SAX-like streaming XML parser (no external dependencies)
class StreamingXMLParser {
    constructor() {
        this.buffer = '';
        this.onOpenTag = null;
        this.onCloseTag = null;
        this.onText = null;
        this.onCData = null;
    }

    write(chunk) {
        this.buffer += chunk;
        this.parse();
    }

    end() {
        this.parse();
    }

    parse() {
        let match;
        
        while (true) {
            // Buffer management: don't trim start to preserve whitespace in text nodes
            // But we need to handle whitespace if we are looking for a tag
            if (!this.buffer) break;

            // Check for CDATA
            if (this.buffer.startsWith('<![CDATA[')) {
                const endIdx = this.buffer.indexOf(']]>');
                if (endIdx === -1) break; // Need more data
                const text = this.buffer.slice(9, endIdx);
                if (this.onCData) this.onCData(text);
                this.buffer = this.buffer.slice(endIdx + 3);
                continue;
            }

            // XML declaration or processing instruction
            if (this.buffer.startsWith('<?')) {
                const endIdx = this.buffer.indexOf('?>');
                if (endIdx === -1) break;
                this.buffer = this.buffer.slice(endIdx + 2);
                continue;
            }

            // Comment
            if (this.buffer.startsWith('<!--')) {
                const endIdx = this.buffer.indexOf('-->');
                if (endIdx === -1) break;
                this.buffer = this.buffer.slice(endIdx + 3);
                continue;
            }

            // Closing tag
            if (this.buffer.startsWith('</')) {
                const endIdx = this.buffer.indexOf('>');
                if (endIdx === -1) break;
                const tagName = this.buffer.slice(2, endIdx).trim();
                if (this.onCloseTag) this.onCloseTag(tagName);
                this.buffer = this.buffer.slice(endIdx + 1);
                continue;
            }

            // Opening tag
            if (this.buffer.startsWith('<')) {
                // Find end of tag
                let endIdx = this.buffer.indexOf('>');
                if (endIdx === -1) break;

                const tagContent = this.buffer.slice(1, endIdx);
                const selfClosing = tagContent.endsWith('/');
                const cleanContent = selfClosing ? tagContent.slice(0, -1) : tagContent;

                // Parse tag name and attributes
                const spaceIdx = cleanContent.search(/\s/);
                const tagName = spaceIdx === -1 ? cleanContent : cleanContent.slice(0, spaceIdx);
                const attrString = spaceIdx === -1 ? '' : cleanContent.slice(spaceIdx);

                // Parse attributes
                const attrs = {};
                const attrRegex = /(\w+)="([^"]*)"/g;
                let attrMatch;
                while ((attrMatch = attrRegex.exec(attrString)) !== null) {
                    attrs[attrMatch[1]] = this.decodeXML(attrMatch[2]);
                }

                if (this.onOpenTag) this.onOpenTag({ name: tagName, attributes: attrs, isSelfClosing: selfClosing });
                if (selfClosing && this.onCloseTag) this.onCloseTag(tagName);

                this.buffer = this.buffer.slice(endIdx + 1);
                continue;
            }

            // Text content (including whitespace)
            const nextTagIdx = this.buffer.indexOf('<');
            if (nextTagIdx === -1) {
                // If no tag found, and we are not at end of stream (implied by break), we wait for more data.
                // However, there is a risk: what if the text really doesn't have a tag after it (end of file)?
                // The 'end()' method calls parse() one last time, but no new data added.
                // We should handle that case, but for streaming, we assume well-formed XML ends with >.
                // BUT: We could be parsing text like "  " which is just waiting for <.
                break;
            }
            
            if (nextTagIdx > 0) {
                const text = this.buffer.slice(0, nextTagIdx);
                // Send ALL text, even if whitespace, to preserve formatting
                if (this.onText) this.onText(this.decodeXML(text));
                this.buffer = this.buffer.slice(nextTagIdx);
                continue;
            }
            
            // If nextTagIdx === 0, it means we have '<'.
            // But we already checked startsWith('<') above?
            // Yes, so we shouldn't reach here if buffer starts with '<'.
            // Wait, if nextTagIdx === 0, buffer starts with '<'. 
            // The checks above cover it.
            // If we are here, it means buffer DOES NOT start with '<', '<?', '<!--', etc.
            // So logic flows safely to Text content block.
        }
    }

    decodeXML(str) {
        return str
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&apos;/g, "'")
            .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(dec))
            .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    }
}

// Main parser logic
async function parseXMLFile(file) {
    const parser = new StreamingXMLParser();
    
    const metadata = {
        test_suite_name: null,
        device_fingerprint: null,
        build_id: null,
        build_product: null,
        build_model: null,
        build_type: null,
        security_patch: null,
        android_version: null,
        suite_version: null,
        suite_plan: null,
        suite_build_number: null,
        host_name: null,
        start_time: null,
        end_time: null
    };

    const stats = {
        total_tests: 0,
        passed_tests: 0,
        failed_tests: 0,
        ignored_tests: 0,
        module_abi_pairs: new Set(),         // "module_name:abi" for unique counting
        failed_module_abi_pairs: new Set(),
        xml_modules_done: 0,                  // From XML <Summary modules_done>
        xml_modules_total: 0                  // From XML <Summary modules_total>
    };

    const failures = [];
    
    // State tracking
    let currentModule = null;
    let currentModuleAbi = null;
    let currentClass = null;
    let currentTest = null;
    let currentFailure = null;
    let collectingStackTrace = false;
    let stackTraceText = '';

    parser.onOpenTag = (tag) => {
        switch (tag.name) {
            case 'Result':
                metadata.test_suite_name = tag.attributes.suite_name || null;
                metadata.suite_version = tag.attributes.suite_version || null;
                metadata.suite_plan = tag.attributes.suite_plan || null;
                metadata.suite_build_number = tag.attributes.suite_build_number || null;
                metadata.host_name = tag.attributes.host_name || null;
                metadata.start_time = tag.attributes.start || null;
                metadata.end_time = tag.attributes.end || null;
                break;

            case 'Build':
                metadata.device_fingerprint = tag.attributes.build_fingerprint || null;
                metadata.build_id = tag.attributes.build_id || null;
                metadata.build_product = tag.attributes.build_product || null;
                metadata.build_model = tag.attributes.build_model || null;
                metadata.build_type = tag.attributes.build_type || null;
                metadata.security_patch = tag.attributes.build_version_security_patch || null;
                metadata.android_version = tag.attributes.build_version_release || null;
                break;

            case 'Summary':
                stats.xml_modules_done = parseInt(tag.attributes.modules_done || '0', 10);
                stats.xml_modules_total = parseInt(tag.attributes.modules_total || '0', 10);
                break;

            case 'Module':
                currentModule = tag.attributes.name || 'Unknown';
                currentModuleAbi = tag.attributes.abi || 'Unknown';
                // Use module:abi as unique key to properly count ABI variants
                stats.module_abi_pairs.add(`${currentModule}:${currentModuleAbi}`);
                break;

            case 'TestCase':
                currentClass = tag.attributes.name || 'Unknown';
                break;

            case 'Test':
                currentTest = {
                    module_name: currentModule,
                    module_abi: currentModuleAbi,
                    class_name: currentClass,
                    method_name: tag.attributes.name || 'Unknown',
                    status: tag.attributes.result || 'unknown',
                    error_message: null,
                    stack_trace: null
                };
                
                stats.total_tests++;
                if (currentTest.status === 'pass') {
                    stats.passed_tests++;
                } else if (currentTest.status === 'fail') {
                    stats.failed_tests++;
                    stats.failed_module_abi_pairs.add(`${currentModule}:${currentModuleAbi}`);
                } else {
                    stats.ignored_tests++;
                }
                break;

            case 'Failure':
                if (currentTest) {
                    currentTest.error_message = tag.attributes.message || null;
                    currentFailure = currentTest;
                    // Start collecting potential direct text stack trace
                    // Buffer is reset here, but if there's a subsequent StackTrace tag, it will reset again.
                    // This allows capturing text directly inside Failure.
                    stackTraceText = '';
                    collectingStackTrace = true;
                }
                break;

            case 'StackTrace':
                collectingStackTrace = true;
                stackTraceText = '';
                break;
        }
    };

    parser.onText = (text) => {
        if (collectingStackTrace) {
            stackTraceText += text;
        }
    };

    parser.onCData = (text) => {
        if (collectingStackTrace) {
            stackTraceText += text;
        }
    };

    parser.onCloseTag = (tagName) => {
        switch (tagName) {
            case 'StackTrace':
                if (currentFailure && stackTraceText.trim()) {
                    currentFailure.stack_trace = stackTraceText.trim();
                }
                collectingStackTrace = false;
                // Don't clear stackTraceText yet, let Failure close handle fallback if needed?
                // Actually, if we had a StackTrace tag, we are done.
                // If we treat Failure content as fallback, we don't want to mix them.
                stackTraceText = ''; 
                break;

            case 'Failure':
                // Get stack trace from collected text if not in StackTrace element
                // And only if we have collected something (maybe just whitespace?)
                if (currentFailure && !currentFailure.stack_trace && stackTraceText.trim()) {
                    currentFailure.stack_trace = stackTraceText.trim();
                }
                collectingStackTrace = false;
                break;

            case 'Test':
                if (currentTest && currentTest.status === 'fail') {
                    failures.push({ ...currentTest });
                }
                currentTest = null;
                currentFailure = null;
                break;

            case 'TestCase':
                currentClass = null;
                break;

            case 'Module':
                currentModule = null;
                currentModuleAbi = null;
                break;
        }
    };

    // Stream read the file
    const reader = file.stream().getReader();
    const decoder = new TextDecoder('utf-8');
    let bytesRead = 0;
    const totalBytes = file.size;
    let lastProgressReport = 0;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        bytesRead += value.length;
        const chunk = decoder.decode(value, { stream: true });
        parser.write(chunk);

        // Report progress every 1%
        const percent = Math.floor((bytesRead / totalBytes) * 100);
        if (percent > lastProgressReport) {
            lastProgressReport = percent;
            self.postMessage({
                type: 'progress',
                percent: percent,
                bytesRead: bytesRead,
                totalBytes: totalBytes,
                testsProcessed: stats.total_tests
            });
        }
    }

    parser.end();

    // Build final result
    const result = {
        metadata: metadata,
        stats: {
            total_tests: stats.total_tests,
            passed_tests: stats.passed_tests,
            failed_tests: stats.failed_tests,
            ignored_tests: stats.ignored_tests,
            total_modules: stats.module_abi_pairs.size,
            passed_modules: stats.module_abi_pairs.size - stats.failed_module_abi_pairs.size,
            failed_modules: stats.failed_module_abi_pairs.size,
            xml_modules_done: stats.xml_modules_done,
            xml_modules_total: stats.xml_modules_total
        },
        failures: failures
    };

    return result;
}

// Worker message handler
self.onmessage = async function(e) {
    try {
        const file = e.data;
        
        self.postMessage({
            type: 'progress',
            percent: 0,
            bytesRead: 0,
            totalBytes: file.size,
            testsProcessed: 0
        });

        const result = await parseXMLFile(file);

        self.postMessage({
            type: 'complete',
            result: result
        });
    } catch (error) {
        self.postMessage({
            type: 'error',
            error: error.message || 'Unknown parsing error'
        });
    }
};
