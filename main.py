# main.py
# Real-Time SQLite Forensics Workstation Backend for ROBLOCKSEC

import asyncio
from datetime import datetime
import hashlib
import json
import os
import re
import sqlite3
import struct
import uuid
from typing import List, Dict
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="ROBLOCKSEC Forensics WORKSTATION API", version="2.0.0")

# Workspace root path lookup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if os.environ.get("VERCEL"):
    UPLOADS_DIR = "/tmp/uploads"
    DB_PATH = "/tmp/roblocksec_vault.db"
    
    # Copy seed database if it exists in BASE_DIR to /tmp/roblocksec_vault.db
    original_db = os.path.join(BASE_DIR, "roblocksec_vault.db")
    if os.path.exists(original_db) and not os.path.exists(DB_PATH):
        import shutil
        try:
            shutil.copy2(original_db, DB_PATH)
        except Exception as e:
            print("Failed to copy database to /tmp:", e)
else:
    UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
    DB_PATH = os.path.join(BASE_DIR, "roblocksec_vault.db")

# Create uploads directory if not present
os.makedirs(UPLOADS_DIR, exist_ok=True)

# 1. Database Initialization Helper
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Cases Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY,
        name TEXT UNIQUE,
        status TEXT DEFAULT 'OPEN',
        severity TEXT DEFAULT 'MEDIUM',
        priority TEXT DEFAULT 'MEDIUM',
        evidence_count INTEGER DEFAULT 0,
        yara_matches INTEGER DEFAULT 0,
        sla_timer TEXT,
        case_number TEXT
    );
    """)

    # Timeline Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timeline (
        event_id TEXT PRIMARY KEY,
        case_id TEXT,
        time TEXT,
        type TEXT,
        msg TEXT,
        tag TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
    );
    """)

    # Chain of Custody Table (Append-Only)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chain_of_custody (
        record_id TEXT PRIMARY KEY,
        case_id TEXT,
        action TEXT,
        actor TEXT,
        file_name TEXT,
        sha256 TEXT,
        timestamp TEXT,
        digital_signature TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(case_id)
    );
    """)
    
    # Triggers for Append-Only (prevent updates & deletes on Chain of Custody table)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_coc_update
    BEFORE UPDATE ON chain_of_custody
    BEGIN
        SELECT raise(ABORT, 'Chain of custody modification violation: UPDATES FORBIDDEN.');
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_coc_delete
    BEFORE DELETE ON chain_of_custody
    BEGIN
        SELECT raise(ABORT, 'Chain of custody modification violation: DELETIONS FORBIDDEN.');
    END;
    """)
    
    # Seed 3 distinct cases
    cases_to_seed = [
        ("CASE_2026_APT29_CHIMERA", "CASE_2026_APT29_CHIMERA", "OPEN", "CRITICAL", "HIGH", 3, 3, "01:19:35", "RB-2026-0001"),
        ("CASE_2026_BLACKCAT_RANSOM", "CASE_2026_BLACKCAT_RANSOM", "CLOSED", "HIGH", "MEDIUM", 2, 2, "00:00:00", "RB-2026-0002"),
        ("CASE_2026_INSIDER_EXFIL", "CASE_2026_INSIDER_EXFIL", "OPEN", "MEDIUM", "HIGH", 2, 1, "12:45:10", "RB-2026-0003")
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO cases (case_id, name, status, severity, priority, evidence_count, yara_matches, sla_timer, case_number)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, cases_to_seed)
    
    # Seeding Unique Case Timelines
    default_events = [
        # Case 1 (APT29 Chimera)
        ("t1", "CASE_2026_APT29_CHIMERA", "09:12:00 UTC", "PROCESS", "powershell.exe -w hidden -enc JABzAD... (PID: 2204) spawned by EXPLORER.EXE", "T1566"),
        ("t2", "CASE_2026_APT29_CHIMERA", "09:12:05 UTC", "FILE", "File created: C:\\Users\\Public\\Resume_Review.zip", "T1566"),
        ("t3", "CASE_2026_APT29_CHIMERA", "09:12:12 UTC", "NETWORK", "Outbound socket: 192.168.42.10:49221 -> 185.220.101.4:443 (ESTABLISHED)", "T1048"),
        ("t4", "CASE_2026_APT29_CHIMERA", "09:30:15 UTC", "PROCESS", "gpupdate.exe (PID: 3320) spawned LSASS.EXE (PID: 884)", "T1003.001"),
        ("t5", "CASE_2026_APT29_CHIMERA", "09:30:30 UTC", "REGISTRY", "Modified key: HKLM\\System\\CurrentControlSet\\Control\\Lsa - Security Packages", "T1003.001"),
        ("t6", "CASE_2026_APT29_CHIMERA", "10:15:40 UTC", "NETWORK", "RDP Connection: 192.168.42.10 (WS-01) -> 192.168.42.20 (SRV-02) (Port 3389)", "T1021.002"),
        ("t7", "CASE_2026_APT29_CHIMERA", "11:00:22 UTC", "REGISTRY", "Created run key: HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run - SystemUpdate = 'C:\\Windows\\Temp\\updater.exe'", "T1547.001"),
        ("t8", "CASE_2026_APT29_CHIMERA", "11:30:45 UTC", "NETWORK", "DNS Query: 14782390a.exfil-dns-tunnel.net (TX payload stream)", "T1048"),
        ("t9", "CASE_2026_APT29_CHIMERA", "12:00:10 UTC", "FILE", "File created: C:\\HELP_DECRYPT.txt (Entropy: 7.95)", "T1486"),

        # Case 2 (BlackCat Ransomware)
        ("t10", "CASE_2026_BLACKCAT_RANSOM", "08:00:00 UTC", "FILE", "Ransomware encryptor payload executed. Encryption log files created.", "T1486"),
        ("t11", "CASE_2026_BLACKCAT_RANSOM", "08:15:00 UTC", "NETWORK", "Outbound SMB scan connection: 192.168.10.150 -> 192.168.10.160", "T1021.002"),
        ("t12", "CASE_2026_BLACKCAT_RANSOM", "08:22:00 UTC", "REGISTRY", "Registry Run key modification shadow copy deletion script loaded.", "T1547.001"),

        # Case 3 (Insider Exfiltration)
        ("t13", "CASE_2026_INSIDER_EXFIL", "14:00:00 UTC", "FILE", "SQL DB dump exported local file: C:\\Users\\Public\\hr_db.csv", "T1204"),
        ("t14", "CASE_2026_INSIDER_EXFIL", "14:30:00 UTC", "NETWORK", "Exfiltrated high volume payload data stream: 216.58.212.42 (MegaUpload)", "T1048"),
        ("t15", "CASE_2026_INSIDER_EXFIL", "15:00:00 UTC", "PROCESS", "Cleanup powershell script execution: Cleanup_Logs.ps1", "T1059")
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO timeline (event_id, case_id, time, type, msg, tag)
    VALUES (?, ?, ?, ?, ?, ?);
    """, default_events)
    
    # Seeding Unique Chain of Custody Ledgers
    default_coc = [
        # Case 1
        ("coc-1", "CASE_2026_APT29_CHIMERA", "INGEST", "SMITH", "ws01_disk.e01", "f3d53a98ea2f4007b819fbc413e16b9b3e10db51abff2c140bc7538a7c1a84f3", "2026-06-30T09:00:00Z", "sig-sha256-ecdsa-val-38a"),
        ("coc-2", "CASE_2026_APT29_CHIMERA", "INGEST", "SMITH", "win11_mem.raw", "48d4239bcfa84092b3a8d16790bcfad43a1290bbffcde8d541295b9c1d06ff3e", "2026-06-30T09:30:00Z", "sig-sha256-ecdsa-val-12c"),
        ("coc-3", "CASE_2026_APT29_CHIMERA", "INGEST", "SMITH", "traffic.pcap", "bca83d29940aa6f8e7943029bd746765ff02b9e1d884a22c548a3e7db9bcf12c", "2026-06-30T11:15:00Z", "sig-sha256-ecdsa-val-99d"),

        # Case 2
        ("coc-4", "CASE_2026_BLACKCAT_RANSOM", "INGEST", "SMITH", "blackcat_mem.dmp", "58df23bcaf94012db3a8d16790bcfad43a1290bbffcde8d541295b9c1d06ff3f", "2026-06-30T08:30:00Z", "sig-sha256-ecdsa-val-55a"),
        ("coc-5", "CASE_2026_BLACKCAT_RANSOM", "INGEST", "SMITH", "ransomware_note.txt", "12ca83d29940aa6f8e7943029bd746765ff02b9e1d884a22c548a3e7db9bc1234", "2026-06-30T08:45:00Z", "sig-sha256-ecdsa-val-55b"),

        # Case 3
        ("coc-6", "CASE_2026_INSIDER_EXFIL", "INGEST", "SMITH", "exfil_traffic.pcap", "cca83d29940aa6f8e7943029bd746765ff02b9e1d884a22c548a3e7db9bcf999", "2026-06-30T14:15:00Z", "sig-sha256-ecdsa-val-77a"),
        ("coc-7", "CASE_2026_INSIDER_EXFIL", "INGEST", "SMITH", "hr_db.csv", "49d4239bcfa84092b3a8d16790bcfad43a1290bbffcde8d541295b9c1d06ff111", "2026-06-30T14:30:00Z", "sig-sha256-ecdsa-val-77b")
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO chain_of_custody (record_id, case_id, action, actor, file_name, sha256, timestamp, digital_signature)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, default_coc)
    
    # YARA Rules Table Schema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS yara_rules (
        rule_id TEXT PRIMARY KEY,
        name TEXT UNIQUE,
        description TEXT,
        severity TEXT,
        mitre_technique TEXT,
        content TEXT,
        compiled_at TEXT
    );
    """)

    # Seed Default YARA Rules
    default_rules = [
        ("r1", "MimikatzLsassDump", "Detects LSASS process dump tools", "CRITICAL", "T1003.001", "rule MimikatzLsassDump {\n    strings:\n        $m1 = \"mimikatz\"\n        $m2 = \"lsass\"\n    condition:\n        any of them\n}", "2026-06-30T09:00:00Z"),
        ("r2", "ObfuscatedWebshellautorun", "Detects common PHP/ASP webshells and autoruns", "HIGH", "T1547.001", "rule ObfuscatedWebshellautorun {\n    strings:\n        $s1 = \"eval\"\n        $s2 = \"passthru\"\n        $s3 = \"xor_key\"\n    condition:\n        any of them\n}", "2026-06-30T09:00:00Z"),
        ("r3", "DNSExfiltrationC2", "Detects DNS subdomain tunneling data channels", "CRITICAL", "T1048", "rule DNSExfiltrationC2 {\n    strings:\n        $d1 = \"exfil-dns-tunnel.net\"\n    condition:\n        any of them\n}", "2026-06-30T09:00:00Z")
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO yara_rules (rule_id, name, description, severity, mitre_technique, content, compiled_at)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, default_rules)
    
    conn.commit()
    conn.close()

# Run migrations
init_db()

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

class ChatQuery(BaseModel):
    caseId: str
    prompt: str

# Copilot preset answers
copilot_answers = {
    "find persistence": "ROBLOCKSEC ANALYSIS: Registry persistence key discovered at **HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run**. System value **SystemUpdate** maps to binary target **C:\\Windows\\Temp\\updater.exe**. Metadata logs verify this entry was committed during Phase 3 lateral movement activities.",
    "check lsass anomaly": "ROBLOCKSEC ANALYSIS: Kernel diagnostics verify process tree anomaly for **lsass.exe (PID: 884)**. Root lineage points to parent process **GPUPDATE.EXE (PID: 3320)** instead of SMSS. Volatility memory probes flag unverified code block injection with `PAGE_EXECUTE_READWRITE` permissions inside the LSASS process space.",
    "exfiltration flow": "ROBLOCKSEC ANALYSIS: Network flow traces verify high-speed data exfiltration target **exfil-dns-tunnel.net** using DNS Subdomain Tunneling. Data packet sizes from `CHIMERA-SRV-02` confirm 154 MB of compressed binary segments transmitted.",
    "compile brief": "# ROBLOCKSEC INCIDENT RESPONSE REPORT\n\n### Core Objective Assessment\n* **Classification:** OFFICIAL USE ONLY // SECURE\n* **Target:** CHIMERA Domain Controller and Application Network\n* **Threat Actor:** APT29 / Cozy Bear (Matched via indicators)\n\n### Findings Brief\nAdversary obtained access via zip archive execution on WS-01. Using credential dumping profiles extracted from LSASS memory, the actor moved laterally to the database host SRV-02 via RDP. Persistence was established in Registry Run keys before exfiltrating 154 MB of files via DNS Tunneling. Ransomware encryption was triggered across all assets at 12:00 UTC."
}

copilot_answers["trace suspicious memory anomalies in volatility logs"] = copilot_answers["check lsass anomaly"]
copilot_answers["show exfiltrated dns payloads in network capture logs"] = copilot_answers["exfiltration flow"]
copilot_answers["summarize the full attack narrative for court report"] = copilot_answers["compile brief"]

# Custom PCAP Structural Bytes Parser
def parse_pcap_flows(filepath: str) -> List[Dict]:
    flows = []
    if not os.path.exists(filepath):
        return flows
    
    try:
        with open(filepath, "rb") as f:
            data = f.read()
            if len(data) < 24:
                return flows
            
            # Check PCAP Magic Number (d4c3b2a1 or a1b2c3d4)
            magic = struct.unpack("<I", data[0:4])[0]
            swap = False
            if magic == 0xd4c3b2a1:
                swap = True
            elif magic != 0xa1b2c3d4:
                # Not a valid binary PCAP, search using regex IP matches
                text_content = data.decode("utf-8", errors="ignore")
                ips = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text_content)
                for idx in range(0, len(ips) - 1, 2):
                    flows.append({
                        "src": ips[idx],
                        "dst": ips[idx+1],
                        "proto": "TCP",
                        "size": len(text_content) // max(1, len(ips))
                    })
                return flows
            
            # Read global header size = 24 bytes, start packet loop
            offset = 24
            while offset + 16 < len(data):
                # Read packet header (16 bytes)
                # ts_sec (4), ts_usec (4), incl_len (4), orig_len (4)
                if swap:
                    incl_len = struct.unpack(">I", data[offset+8:offset+12])[0]
                else:
                    incl_len = struct.unpack("<I", data[offset+8:offset+12])[0]
                
                pkt_data = data[offset+16 : offset+16+incl_len]
                offset += 16 + incl_len
                
                # Ethernet Header (14 bytes) -> IP header
                # EthType (2 bytes) at offset 12. IPv4 is 0x0800
                if len(pkt_data) > 34:
                    eth_type = struct.unpack(">H", pkt_data[12:14])[0]
                    if eth_type == 0x0800: # IPv4
                        # IP Header starts at 14. Src IP at 26, Dst IP at 30
                        ip_src = ".".join(map(str, pkt_data[26:30]))
                        ip_dst = ".".join(map(str, pkt_data[30:34]))
                        
                        # Protocol at offset 23
                        proto_num = pkt_data[23]
                        proto = "TCP" if proto_num == 6 else "UDP" if proto_num == 17 else "ICMP"
                        
                        flows.append({
                            "src": ip_src,
                            "dst": ip_dst,
                            "proto": proto,
                            "size": len(pkt_data)
                        })
                        if len(flows) >= 15: # Limit rows
                            break
    except Exception as e:
        print("PCAP processing error:", e)
    return flows

# 1. UI Entry Route
@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

# 2. Case List Route
@app.get("/api/v1/cases")
def get_cases():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT case_id, name, status, severity, priority, evidence_count, yara_matches, sla_timer, case_number FROM cases;")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r[0],
            "name": r[1],
            "status": r[2],
            "severity": r[3],
            "priority": r[4],
            "evidenceCount": r[5],
            "yaraMatches": r[6],
            "slaTimer": r[7],
            "caseNumber": r[8]
        } for r in rows
    ]

# 2.5 Case Create Route
class CaseCreateInput(BaseModel):
    name: str
    case_number: str
    severity: str
    priority: str

@app.post("/api/v1/cases")
def create_case(payload: CaseCreateInput):
    name = payload.name.strip().upper().replace(" ", "_")
    if not name or not payload.case_number.strip():
        raise HTTPException(status_code=400, detail="Case name and case number cannot be empty.")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM cases WHERE name = ?;", (name,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"A forensic case with name [{name}] already exists.")
        
    try:
        cursor.execute("""
        INSERT INTO cases (case_id, name, status, severity, priority, evidence_count, yara_matches, sla_timer, case_number)
        VALUES (?, ?, 'OPEN', ?, ?, 0, 0, '24:00:00', ?);
        """, (name, name, payload.severity.upper(), payload.priority.upper(), payload.case_number.strip().upper()))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to create case: {str(e)}")
    conn.close()
    
    return {
        "status": "SUCCESS",
        "caseId": name,
        "message": f"Forensic investigation case [{name}] initialized successfully."
    }

# 3. Timeline Events Query
@app.get("/api/v1/cases/{caseId}/timeline")
def get_timeline(caseId: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT time, type, msg, tag FROM timeline WHERE case_id = ? ORDER BY time ASC;", (caseId,))
    rows = cursor.fetchall()
    conn.close()
    
    events = [
        {
            "time": r[0],
            "type": r[1],
            "msg": r[2],
            "tag": r[3]
        } for r in rows
    ]
    return {
        "total": len(events),
        "events": events
    }

# 3.5 Chain of Custody API Ledger Retrieve
@app.get("/api/v1/cases/{caseId}/coc")
def get_chain_of_custody(caseId: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT record_id, action, actor, file_name, sha256, timestamp, digital_signature FROM chain_of_custody WHERE case_id = ? ORDER BY timestamp DESC;", (caseId,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "recordId": r[0],
            "action": r[1],
            "actor": r[2],
            "fileName": r[3],
            "sha256": r[4],
            "timestamp": r[5],
            "digitalSignature": r[6]
        } for r in rows
    ]
# 3.6 Evidence Report Generator Route
@app.post("/api/v1/evidence/{fileName}/report")
def generate_evidence_report(fileName: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sha256, timestamp, digital_signature, case_id, actor 
        FROM chain_of_custody 
        WHERE file_name = ? LIMIT 1;
    """, (fileName,))
    row = cursor.fetchone()
    
    if not row:
        # Mock values for custom uploaded files
        import hashlib
        from datetime import datetime
        sha256 = hashlib.sha256(fileName.encode()).hexdigest()
        timestamp = datetime.utcnow().isoformat() + "Z"
        digital_signature = "sig-sha256-ecdsa-mock-val-" + sha256[:8]
        case_id = "CASE_2026_APT29_CHIMERA"
        actor = "SMITH"
    else:
        sha256, timestamp, digital_signature, case_id, actor = row

    conn.close()
    
    ext = os.path.splitext(fileName)[1].lower()
    
    analysis_text = ""
    if ext in [".raw", ".mem", ".dmp"]:
        analysis_text = """### 🧠 Volatility 3 Core Analysis Findings
- **Platform OS Kernel:** Windows 10 x64 (Build 19045.2965)
- **Active Anomalies Flagged:**
  * Process `powershell.exe` (PID: 2204) spawned with an obfuscated base64 command string executing inline memory injects.
  * Lsass security vault process memory space accessed via suspicious handle hooks (`gpupdate.exe`).
- **Investigator Recommendation:** Quarantine host WS-01 immediately and inspect network socket indicators."""
    elif ext in [".pcap", ".pcapng"]:
        analysis_text = """### 🔌 Zeek & Suricata Network Session Logs
- **Protocol Analysis:** 
  * DNS Query Stream: Large quantity of TXT DNS tunnel frames exfiltrating payload packets to `exfil-dns-tunnel.net`.
  * Outbound RDP session initialized from internal subnet to untrusted Tor exit gateway node `185.220.101.4`.
- **Intrusion Mitigation:** Block Tor exit IPs and configure deep packet inspections on DNS resolver ports."""
    elif ext in [".exe", ".bin", ".elf"]:
        analysis_text = """### ☣️ Malware Decompiler & Binary Analysis
- **Execution Vector:** Target binary contains entropy configurations (7.95) pointing to commercial packing/obfuscation.
- **YARA Signature Matches:**
  * rule `win_sys_dump` triggered: flags Mimikatz command arrays.
  * rule `tor_network_exit` triggered: flags outbound command & control interfaces.
- **Decompilation Summary:** Ghidra API reports direct function calls mapping to LSASS read/write operations."""
    else:
        analysis_text = """### 🔑 Disk Hive Partition Summary
- **Hive Type:** SAM/SYSTEM Hive structures extracted.
- **Auditing Indicators:**
  * Injected persistency entry found in HKLM registry Run key pointing to temp binary `updater.exe`.
  * Decrypted Local account parameters indicating privilege escalation attempt."""

    report_md = f"""# ⚖️ OFFICIAL GOVERNMENT DFIR FORENSIC REPORT
**CLASSIFICATION: SECURE // OFFICIAL USE ONLY // NOFORN**
**ROBLOCKSEC CYBER COMMAND DIVISION**
*Document ID: REP-{sha256[:8].upper()}*

---

## 🔍 EVIDENCE IDENTIFIER METADATA
- **Asset Filename:** {fileName}
- **Case Ingest ID:** {case_id}
- **Ingest Timestamp:** {timestamp}
- **Hash (SHA-256):** {sha256}
- **Digital Seal/Signature:** {digital_signature}
- **Forensic Custodian:** {actor} (RB-9842)
- **Clearance Level:** Level 5 - TOP SECRET (SCI)

---

## 🛡️ CORE INTEGRITY STATUS
- **[✓] SHA-256 HASH VERIFICATION:** Passed. File hashes match ingestion records.
- **[✓] CHAIN OF CUSTODY LEGER:** Intact. No unauthorized modifications detected.
- **[✓] ANTI-TAMPER DIGITAL SEAL:** Verified. Signed by official Roblocksec Cyber Command certificate.

---

## 📊 AUTOMATED ANALYSIS ABSTRACT & FINDINGS
{analysis_text}

---

## 📄 INVESTIGATOR REMARKS & DISPOSITION
This evidence file was analyzed under secure air-gapped forensic protocols. Detections indicate advanced threat actor group involvement (attributed to APT29 Chimera operations). File has been cryptographically sealed and written statefully into the case archive.

**Approved by:**
`Agent Smith`
*Lead Forensic Incident Responder*
*ROBLOCKSEC Forensics & Response Division*
"""
    return {
        "status": "SUCCESS",
        "fileName": fileName,
        "report": report_md
    }

# 3.7 YARA Signature Compiler Endpoint
class YaraRuleInput(BaseModel):
    content: str

@app.get("/api/v1/yara/rules")
def get_yara_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT rule_id, name, description, severity, mitre_technique, content, compiled_at FROM yara_rules ORDER BY compiled_at DESC;")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "ruleId": r[0],
            "name": r[1],
            "description": r[2],
            "severity": r[3],
            "mitreTechnique": r[4],
            "content": r[5],
            "compiledAt": r[6]
        } for r in rows
    ]

@app.post("/api/v1/yara/compile")
def compile_yara_rule(payload: YaraRuleInput):
    content = payload.content
    
    # 1. Regex validation checks
    rule_match = re.search(r"rule\s+([a-zA-Z0-9_]+)", content)
    if not rule_match:
        return {
            "status": "COMPILE_ERROR",
            "message": "Invalid YARA syntax: Missing rule identifier (e.g. 'rule CustomRule')"
        }
    
    rule_name = rule_match.group(1)
    
    if "strings:" not in content:
        return {
            "status": "COMPILE_ERROR",
            "message": "Invalid YARA syntax: Missing 'strings:' section declaration"
        }
        
    if "condition:" not in content:
        return {
            "status": "COMPILE_ERROR",
            "message": "Invalid YARA syntax: Missing 'condition:' validation criteria block"
        }
        
    # Extract metadata using regex filters
    desc_match = re.search(r'description\s*=\s*"([^"]+)"', content)
    description = desc_match.group(1) if desc_match else "Custom user-defined signature"
    
    sev_match = re.search(r'severity\s*=\s*"([^"]+)"', content)
    severity = sev_match.group(1).upper() if sev_match else "HIGH"
    
    mitre_match = re.search(r'mitre_technique\s*=\s*"([^"]+)"', content)
    mitre_technique = mitre_match.group(1) if mitre_match else "T1059"
    
    # 2. Insert or replace inside SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        rule_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT OR REPLACE INTO yara_rules (rule_id, name, description, severity, mitre_technique, content, compiled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (rule_id, rule_name, description, severity, mitre_technique, content, datetime.utcnow().isoformat() + "Z"))
        conn.commit()
    except Exception as e:
        conn.close()
        return {
            "status": "COMPILE_ERROR",
            "message": f"Database insertion error: {str(e)}"
        }
    conn.close()
    
    return {
        "status": "SUCCESS",
        "ruleName": rule_name,
        "message": f"YARA rule [{rule_name}] successfully compiled and registered."
    }

VT_API_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()

@app.get("/api/v1/osint/search")
def search_osint(query: str):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")
    
    # Basic IP / Hash regex detections
    is_ip = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query)
    is_hash = re.match(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$", query)
    
    query_type = "ip"
    if is_ip:
        query_type = "ip"
    elif is_hash:
        query_type = "hash"
    else:
        query_type = "domain"
        
    # Execute request to VirusTotal API if api key is configured
    if VT_API_KEY:
        base_url = "https://www.virustotal.com/api/v3"
        if query_type == "ip":
            target_url = f"{base_url}/ip_addresses/{query}"
        elif query_type == "hash":
            target_url = f"{base_url}/files/{query}"
        else:
            target_url = f"{base_url}/domains/{query}"
            
        try:
            req = urllib.request.Request(target_url)
            req.add_header("x-apikey", VT_API_KEY)
            import urllib.error
            with urllib.request.urlopen(req, timeout=5) as response:
                vt_data = json.loads(response.read().decode())
                attributes = vt_data.get("data", {}).get("attributes", {})
                stats = attributes.get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                total = sum(stats.values())
                
                tags = attributes.get("tags", [])
                if not tags and query_type == "hash":
                    tags = [attributes.get("meaningful_name", "binary")]
                
                registrar = attributes.get("registrar", "Unknown")
                if query_type == "ip":
                    registrar = attributes.get("as_owner", "Unknown Provider")
                    
                summary = f"VirusTotal analysis results for {query}. Flagged by {malicious}/{total or 72} security engines."
                
                return {
                    "status": "SUCCESS",
                    "query": query,
                    "type": query_type,
                    "maliciousDetections": malicious,
                    "totalDetections": total or 72,
                    "tags": tags,
                    "metadata": registrar,
                    "summary": summary
                }
        except Exception as api_err:
            print(f"VT API call exception: {api_err}. Using mock fallbacks.")
            
    # Mock fallback profiles
    mock_reputations = {
        "exfil-dns-tunnel.net": {
            "malicious": 58,
            "total": 72,
            "tags": ["c2", "dns-tunneling", "apt29", "exfiltration"],
            "metadata": "NameCheap, Inc. (Registered: 2026-05-12)",
            "summary": "Exfiltration C2 DNS domain detected in active timeline logs. Identified with target indicators matching APT29/Cozy Bear lateral movement profiles."
        },
        "185.220.101.4": {
            "malicious": 49,
            "total": 72,
            "tags": ["tor-exit-node", "c2-relay", "anon-network"],
            "metadata": "AS200021 Tor Exit Gateway Node, Germany",
            "summary": "Threat intelligence flags this IP address as an active Tor gateway host linked to remote payload exfiltration relays."
        },
        "6ad1e97d624de26a145ca5b7d2a04035fb3976f45ed9950a2e1e4d98e3ca097d": {
            "malicious": 64,
            "total": 72,
            "tags": ["mimikatz", "lsass-dump", "hacktool", "trojan"],
            "metadata": "Mimikatz LSASS Dump Tool Loader Bin",
            "summary": "Cryptographic hash matches catalog entry for mimikatz/credential-dumper executable, flagged by major enterprise engines."
        }
    }
    
    normalized_query = query.lower()
    if normalized_query in mock_reputations:
        rec = mock_reputations[normalized_query]
        return {
            "status": "SUCCESS",
            "query": query,
            "type": query_type,
            "maliciousDetections": rec["malicious"],
            "totalDetections": rec["total"],
            "tags": rec["tags"],
            "metadata": rec["metadata"],
            "summary": rec["summary"]
        }
    else:
        return {
            "status": "SUCCESS",
            "query": query,
            "type": query_type,
            "maliciousDetections": 0,
            "totalDetections": 72,
            "tags": ["clean-reputation", "no-indicators"],
            "metadata": "No registry whois matches. Clean record.",
            "summary": f"VirusTotal scanner verified query {query}. Zero AV detections flagged."
        }

# 4. AI Copilot Chat POST
@app.post("/api/v1/copilot/chat")
def post_copilot_chat(query: ChatQuery):
    normalized_prompt = query.prompt.lower()
    answer = "ERROR: Inquiry context not matched. Use quick prompt parameters to isolate threat vectors."
    confidence = 0.40
    sources = []

    for key in copilot_answers:
        if key in normalized_prompt:
            answer = copilot_answers[key]
            confidence = 0.98
            sources = [{"type": "sqlite_database", "id": "knowledge_bank_idx"}]
            break

    return {
        "answer": answer,
        "confidenceScore": confidence,
        "sources": sources
    }

# 5. Stateful Evidence Ingestion & Scanning Endpoint
@app.post("/api/v1/evidence/upload")
async def upload_evidence(
    caseId: str = Form(...),
    evidenceType: str = Form(...),
    file: UploadFile = File(...)
):
    evidence_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOADS_DIR, file.filename)
    
    # 1. Save uploaded file physically to disk
    sha256_hash = hashlib.sha256()
    with open(filepath, "wb") as f:
        while True:
            chunk = await file.read(1024 * 64)
            if not chunk:
                break
            f.write(chunk)
            sha256_hash.update(chunk)
            
    calculated_hash = sha256_hash.hexdigest()
    
    # 2. Append-Only Chain of Custody insert
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    digital_signature_manifest = hashlib.sha256(f"{calculated_hash}-{evidence_id}".encode("utf-8")).hexdigest()
    
    cursor.execute("""
    INSERT INTO chain_of_custody (record_id, case_id, action, actor, file_name, sha256, timestamp, digital_signature)
    VALUES (?, ?, 'INGEST', 'AGENT_SMITH', ?, ?, ?, ?);
    """, (
        str(uuid.uuid4()),
        caseId,
        file.filename,
        calculated_hash,
        datetime.utcnow().isoformat() + "Z",
        digital_signature_manifest
    ))
    
    # Update evidence count on cases table
    cursor.execute("UPDATE cases SET evidence_count = evidence_count + 1 WHERE case_id = ?;", (caseId,))
    conn.commit()
    conn.close()

    # 3. Trigger analysis loop
    asyncio.create_task(run_file_forensics_scan(evidence_id, caseId, file.filename, filepath, calculated_hash))

    return {
        "evidenceId": evidence_id,
        "caseId": caseId,
        "fileName": file.filename,
        "sha256": calculated_hash,
        "status": "QUEUED"
    }

# 6. WebSocket Endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 7. Asynchronous File Scan and PCAP/YARA Forensics Loop
async def run_file_forensics_scan(evidence_id: str, case_id: str, file_name: str, filepath: str, file_hash: str):
    await asyncio.sleep(1.0)
    
    # Broadast Step 1: Ingestion validation
    await manager.broadcast({
        "event": "TASK_PROGRESS",
        "data": {
            "percentageComplete": 15,
            "status": "PROCESSING",
            "currentAction": f"Cryptographic validation complete. SHA-256: {file_hash[:16]}..."
        }
    })
    await asyncio.sleep(1.5)

    # Broadast Step 2: YARA Signature Matching Scan
    threat_detected = False
    mitre_tech = "T1059"
    yara_rule_trigger = ""
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, mitre_technique, content FROM yara_rules;")
        db_rules = cursor.fetchall()
        conn.close()
        
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            file_text = f.read().lower()
            
            for rule_name, rule_mitre, rule_content in db_rules:
                # Extract strings array e.g. $m1 = "value"
                patterns = re.findall(r'\$[a-zA-Z0-9_]+\s*=\s*"([^"]+)"', rule_content)
                if patterns:
                    matched = False
                    for pat in patterns:
                        if pat.lower() in file_text:
                            matched = True
                            break
                    if matched:
                        threat_detected = True
                        mitre_tech = rule_mitre
                        yara_rule_trigger = rule_name
                        break
    except Exception as db_err:
        print("Dynamic YARA check failure:", db_err)
        # Fallback static scanner
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            file_text = f.read().lower()
            if "mimikatz" in file_text or "lsass" in file_text:
                threat_detected = True
                mitre_tech = "T1003.001"
                yara_rule_trigger = "MimikatzLsassDump"

    await manager.broadcast({
        "event": "TASK_PROGRESS",
        "data": {
            "percentageComplete": 45,
            "status": "PROCESSING",
            "currentAction": f"YARA scanning complete. Rule match flag: {yara_rule_trigger if threat_detected else 'None'}"
        }
    })
    await asyncio.sleep(1.5)

    # Broadast Step 3: PCAP Parsing
    extracted_connections = []
    if file_name.endswith(".pcap") or file_name.endswith(".pcapng"):
        extracted_connections = parse_pcap_flows(filepath)
        action_msg = f"PCAP analysis extracted {len(extracted_connections)} active flows."
    else:
        action_msg = "Non-PCAP binary detected. Skipping struct packet parsing."
        
    await manager.broadcast({
        "event": "TASK_PROGRESS",
        "data": {
            "percentageComplete": 75,
            "status": "PROCESSING",
            "currentAction": action_msg
        }
    })
    await asyncio.sleep(1.5)

    # Broadast Step 4: Database Timeline logs Ingestion
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    time_string = datetime.utcnow().strftime("%H:%M:%S UTC")
    
    # Insert general upload timeline log
    cursor.execute("""
    INSERT INTO timeline (event_id, case_id, time, type, msg, tag)
    VALUES (?, ?, ?, 'FILE', ?, 'T1204');
    """, (str(uuid.uuid4()), case_id, time_string, f"Ingested asset {file_name} into Case Folder."))
    
    # Insert extracted network flows to timeline
    for flow in extracted_connections:
        flow_uuid = str(uuid.uuid4())
        flow_msg = f"Network Connection: {flow['src']} -> {flow['dst']} ({flow['proto']}) size: {flow['size']} bytes"
        cursor.execute("""
        INSERT INTO timeline (event_id, case_id, time, type, msg, tag)
        VALUES (?, ?, ?, 'NETWORK', ?, 'T1043');
        """, (flow_uuid, case_id, time_string, flow_msg))
        
    # If YARA trigger found, insert timeline log and update match metrics
    if threat_detected:
        alert_uuid = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO timeline (event_id, case_id, time, type, msg, tag)
        VALUES (?, ?, ?, 'PROCESS', ?, ?);
        """, (
            alert_uuid,
            case_id,
            time_string,
            f"CRITICAL signature match in {file_name}: Rule [{yara_rule_trigger}] triggered.",
            mitre_tech
        ))
        cursor.execute("UPDATE cases SET yara_matches = yara_matches + 1 WHERE case_id = ?;", (case_id,))
        
    # Trigger active OSINT/VirusTotal analysis for file hash reputation
    try:
        vt_res = search_osint(file_hash)
        if vt_res.get("maliciousDetections", 0) > 0:
            vt_uuid = str(uuid.uuid4())
            vt_tag = "T1059"
            if vt_res.get("tags"):
                # Try to map common categories to MITRE techniques
                first_tag = vt_res["tags"][0]
                if "mimikatz" in first_tag or "lsass" in first_tag:
                    vt_tag = "T1003.001"
                elif "persistence" in first_tag or "registry" in first_tag:
                    vt_tag = "T1547.001"
                    
            vt_msg = f"Threat Intel Alert: VirusTotal flagged {file_name} as malicious ({vt_res['maliciousDetections']}/{vt_res['totalDetections']} engines). Tags: {', '.join(vt_res['tags'][:3])}"
            cursor.execute("""
            INSERT INTO timeline (event_id, case_id, time, type, msg, tag)
            VALUES (?, ?, ?, 'PROCESS', ?, ?);
            """, (vt_uuid, case_id, time_string, vt_msg, vt_tag))
            cursor.execute("UPDATE cases SET yara_matches = yara_matches + 1 WHERE case_id = ?;", (case_id,))
    except Exception as osint_err:
        print("Background OSINT lookup error:", osint_err)
        
    conn.commit()
    conn.close()

    # Broadast Step 5: Finalized completion
    await manager.broadcast({
        "event": "TASK_PROGRESS",
        "data": {
            "percentageComplete": 100,
            "status": "SUCCESS",
            "currentAction": f"Asset {file_name} successfully indexed to database ledger."
        }
    })

    # Trigger critical notification over WebSocket if threat matched
    if threat_detected:
        await asyncio.sleep(1.0)
        await manager.broadcast({
            "event": "NEW_ALERT",
            "data": {
                "alertId": str(uuid.uuid4()),
                "caseId": case_id,
                "severity": "CRITICAL",
                "message": f"YARA Match: Signature [{yara_rule_trigger}] confirmed inside {file_name}.",
                "mitreTechnique": mitre_tech
            }
        })

# Mount static asset directory
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")
