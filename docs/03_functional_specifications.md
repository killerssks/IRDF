# 03. Functional Specifications

This document outlines the detailed functional specifications of the seven modules forming the core of the **AI-DFIR Platform**. It contains technical requirements, data models, parser logic, AI integration capabilities, and visualization specifications for each component.

---

## 📁 Module 1 — Case Management

The Case Management module coordinates evidence logging, user collaboration, progress tracking, and chain of custody documentation.

### 1.1 Case Dashboard
The landing panel for an investigation. It displays live case metadata fields including:
* **Identification:** Case ID (UUIDv4), Case Name, Department, Assignee (Owner), Tags.
* **Triage Metrics:** Priority (Low, Medium, High, Critical), Severity (Sev 1 - Sev 4), SLA countdown timer.
* **Audit State:** Creation Date, Last Updated Timestamp, Evidence Count, Alerts Count.
* **Widgets:** Summary status graphs showing parsed artifacts progress.

### 1.2 Investigation Workspace
A shared workspace allowing multiple analysts to operate under a single case structure:
* **Multi-Case Workspaces:** Support switching tabs between active concurrent cases.
* **File Directory Canvas:** Dynamic file explorer where images can be cataloged.
* **Drag-and-Drop Ingestion:** Accepts evidence files and queues them automatically.
* **Collaboration Tools:** Notes panel, bookmarks for specific registry keys/lines of code, and threads for investigator comments.
* **Verification Panel:** Calculates and verifies SHA-256 and MD5 hashes, raising alerts if they deviate from initial ingestion values.

### 1.3 Case Timeline & Chronology
A central database of all chronologically ordered events. It parses and aligns:
* User Logins, File Creation, Registry Modifications, Process Execution (Prefetch/Audit logs), Network Connections, USB Insertions, Browser History, Scheduled Tasks, Memory Events, and Threat Detections.

### 1.4 Evidence Repository
* **Artifact Classes:** Disk Images, Memory Dumps, PCAP Logs, Event Logs, Registry Hives, Browser History files, Cloud Tokens, Malware Samples, IoCs, YARA rules, and Sigma rules.

---

## 💾 Module 2 — Image Analysis

The Image Analysis module mounts, parses, and analyzes virtualized disk media and physical device dumps.

### 2.1 Disk Format & Filesystem Support
* **Disk Images:** E01, AFF, RAW, DD, VMDK, VHD, QCOW2.
* **Filesystems:** NTFS, FAT32, exFAT, EXT4, APFS, HFS+.

### 2.2 Forensic Parsing Engine
* Parses the master file table (**MFT**), Slack Space, Recycle Bin files, Alternate Data Streams (**ADS**), LNK files, Jump Lists, Prefetch directories, Shadow Copies, browser history/cookies, and Microsoft Outlook PST/OST emails.

### 2.3 AI-Powered Disk Detection
The backend LLM scans extracted metadata anomalies to flag:
* **Persistence Mechanisms:** Scheduled tasks pointing to temp folders.
* **Living-off-the-Land:** Execution of certutil, powershell with encoded command flags.
* **Credential Dumping:** Shadow copy extraction of `SAM` and `SYSTEM` hives.
* **Data Anomaly:** Hidden partitions and High Entropy (encrypted) folders indicating ransomware activity.

### 2.4 Visualizations
* **Directory Trees & Treemaps:** Represents directory sizing and file allocations.
* **Heatmaps:** Displays write density over specific sector offsets.
* **Entropy Graph:** Plots byte entropy ratios along sectors to locate hidden containers.

---

## 🧠 Module 3 — Memory Forensics

Provides an advanced, interactive interface wrapping the **Volatility 3** engine to audit RAM captures.

### 3.1 Memory Ingestion & Parsing
* **Formats:** RAW, MEM, VMEM, Crash Dumps, HIBERFIL.SYS, PAGEFILE.SYS.
* **Execution:** Wraps Volatility 3 plugin scripts (`windows.pslist`, `windows.malfind`, `windows.registry.printkey`).

### 3.2 Key Forensic Targets
* **Processes & Drivers:** Injected code checks, Process Trees, Kernel Modules, Sockets, and Services.
* **User Context:** Clipboard buffers, Command History, LSASS Tokens, and loaded Mutex lists.

### 3.3 AI Memory Analysis Agent
* Analyzes raw volatility outputs to detect **Reflective Loading**, **DLL Hijacking**, **Process Hollowing**, **LSASS Dumping**, **Kernel Hooks**, and **C2 beacons** hidden in process memory pools.

### 3.4 Visualizations
* **Process Tree:** Hierarchical relationship node map.
* **DLL Dependency Graph:** Highlighting unsigned DLL modules.
* **Memory Map Grid:** Visualizes memory segment permissions (`PAGE_EXECUTE_READWRITE`).

---

## 🔌 Module 4 — Network Traffic Analysis

Performs packet analysis, protocol validation, and network anomaly correlation.

### 4.1 Ingestion Sources
* **PCAP/PCAPNG**, NetFlow files, Zeek connection logs, Suricata IDS alerts, and cloud firewalls log streams (AWS VPC Flow Logs).

### 4.2 Protocol Support
* HTTP, HTTPS, DNS, FTP, SMTP, TLS (JA3 Fingerprints), SMB, LDAP, Kerberos, MQTT, Modbus, ICMP, RDP, and QUIC.

### 4.3 AI Network Inspection
* Identifies **DNS Tunneling**, **Fast-Flux DNS**, **C2 Beaconing intervals** via frequency domain analysis, **Data Exfiltration** via anomalies in output size, and **Lateral Movement** via Kerberos ticketing anomalies.

### 4.4 Visualizations
* **Conversation Graph:** Nodes (IPs) and edges (Packets) sized by bandwidth.
* **GeoIP Map:** Visualizes endpoints on a world map.
* **Flow Heatmap:** Displays active connections over a time-of-day matrix.

---

## 🤖 Module 5 — AI Analysis Summary Panel

Acts as a central knowledge hub summarizing ongoing case work.

### 5.1 Real-Time Synthesis
* Consolidates memory anomalies, network beacons, and host artifacts to calculate a global **Confidence Score** and **Risk Score**.
* Map identified findings automatically to the **MITRE ATT&CK Matrix** (Tactics through Techniques).

### 5.2 Document Compilation Output
Generates detailed report sections:
* **Executive Summary:** A business-risk outline of the incident.
* **Technical Summary:** Details on the entry point, persistence, and impact.
* **Containment & Recovery Steps:** Immediate blocks to apply (firewall ports, domain account disablement).

---

## 🔍 Module 6 — Reverse Engineering Workspace

An integrated malware analysis lab allowing disassembly and decompilation reviews.

### 6.1 Workspace Layout Tabs
* **Decompiler/Disassembly:** C-like pseudocode views and raw instruction disassembly.
* **PE/ELF Headers:** Section offsets, imports table, exports table, resources, and entropy levels.
* **Capabilities Mapping:** Triggers capa rules to map execution behaviors (e.g., "reads credential files").

### 6.2 AI Decompilation Assistant
* Explains compiler-optimized logic in plain language.
* Identifies **API Hashing**, **Obfuscation (packer markers like VMProtect)**, **Anti-Analysis checks (isDebuggerPresent)**, and cryptographic loops.

### 6.3 Visualizations
* **Control Flow Graph (CFG):** Block flow charts displaying execution jumps.
* **Call Graph:** Displays function execution trees.

---

## 🏷️ Module 7 — Artifact Analysis & Threat Intelligence

Integrates external databases and system forensic logs to find IOCs and threat actors.

### 7.1 Key OS Artifact Analyzers
* Parses registry configurations, autoruns, Amcache/Shimcache records, PowerShell script histories, shell cookies, cloud session tokens, and office document metadata.

### 7.2 Threat Intelligence API Hub
* Integrates external threat feeds: VirusTotal, AlienVault OTX, AbuseIPDB, MISP, OpenCTI, URLHaus, Shodan, and CVE/CISA database listings.

### 7.3 AI Threat Correlation
* Scans files, IPs, hashes, mutexes, certificates, and memory profiles to identify if they match indicators associated with known **APT Groups** (e.g., APT29, Cozy Bear) and historic campaigns.
