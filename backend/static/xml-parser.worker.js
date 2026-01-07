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
            // Skip whitespace
            this.buffer = this.buffer.trimStart();
            if (!this.buffer) break;

            // CDATA section
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

            // Text content
            const nextTagIdx = this.buffer.indexOf('<');
            if (nextTagIdx === -1) break;
            if (nextTagIdx > 0) {
                const text = this.buffer.slice(0, nextTagIdx);
                if (this.onText && text.trim()) this.onText(this.decodeXML(text));
                this.buffer = this.buffer.slice(nextTagIdx);
            }
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
        modules: new Set(),
        failed_modules: new Set()
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

            case 'Module':
                currentModule = tag.attributes.name || 'Unknown';
                currentModuleAbi = tag.attributes.abi || 'Unknown';
                stats.modules.add(currentModule);
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
                    stats.failed_modules.add(currentModule);
                } else {
                    stats.ignored_tests++;
                }
                break;

            case 'Failure':
                if (currentTest) {
                    currentTest.error_message = tag.attributes.message || null;
                    currentFailure = currentTest;
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
                stackTraceText = '';
                break;

            case 'Failure':
                // Get stack trace from collected text if not in StackTrace element
                if (currentFailure && !currentFailure.stack_trace && stackTraceText.trim()) {
                    currentFailure.stack_trace = stackTraceText.trim();
                }
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
            total_modules: stats.modules.size,
            passed_modules: stats.modules.size - stats.failed_modules.size,
            failed_modules: stats.failed_modules.size
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
