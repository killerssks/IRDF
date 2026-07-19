# 05. API Specifications

This document defines the interface specifications for communicating with the **AI-DFIR Suite** backend. It details REST API endpoints, WebSocket connection payloads, and GraphQL search structures.

---

## 🔐 REST API Architecture

* **Format:** JSON payloads, camelCase properties.
* **Authentication:** HTTP Authorization header containing a JSON Web Token (JWT):
  `Authorization: Bearer <token>`
* **Status Codes:** Standard HTTP status codes (200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 500 Server Error).

---

## 🛠️ REST Endpoints

### 1. Case Management (`/api/v1/cases`)

#### `POST /api/v1/cases`
* **Purpose:** Initialize a new investigation case folder.
* **Request Payload:**
```json
{
  "name": "Intrusion at HQ Branch",
  "severity": "CRITICAL",
  "priority": "HIGH",
  "department": "Security Operations",
  "tags": ["APT29", "Phishing"]
}
```
* **Response Payload (201 Created):**
```json
{
  "id": "e0e24dd3-1a22-4467-bc18-97c3bb83b0f5",
  "name": "Intrusion at HQ Branch",
  "severity": "CRITICAL",
  "priority": "HIGH",
  "status": "OPEN",
  "ownerId": "f784e1b8-c91f-4bb2-b5b4-d53b6faec992",
  "createdAt": "2026-06-30T22:45:00Z",
  "updatedAt": "2026-06-30T22:45:00Z"
}
```

#### `GET /api/v1/cases/{caseId}/timeline`
* **Purpose:** Retrieve the parsed chronological event list for a case.
* **Query Parameters:** `limit=50`, `offset=0`, `filters=["process", "network"]`.
* **Response (200 OK):**
```json
{
  "total": 1284,
  "events": [
    {
      "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "timestamp": "2026-06-30T22:04:12Z",
      "eventType": "PROCESS",
      "hostName": "PROD-APP-01",
      "message": "Process GPUPDATE.EXE (PID 3320) spawned LSASS.EXE (PID 884)",
      "severity": "HIGH",
      "mitreMapping": "T1003.001"
    }
  ]
}
```

---

### 2. Evidence Ingestion (`/api/v1/evidence`)

#### `POST /api/v1/evidence/upload`
* **Purpose:** Upload a physical file or register a network path to a raw image disk.
* **Content-Type:** `multipart/form-data`
* **Request Fields:** `caseId` (UUID), `file` (Binary), `evidenceType` ("DISK" | "MEM" | "PCAP" | "LOG").
* **Response (202 Accepted):**
```json
{
  "evidenceId": "2bfb44cf-d54e-4f01-8b27-512a149b5c32",
  "caseId": "e0e24dd3-1a22-4467-bc18-97c3bb83b0f5",
  "fileName": "win11_mem.raw",
  "sha256": "8f4384a51e604f3261a86845347fa65e90403e0a137ca25dbcb41e17ca26262b",
  "status": "QUEUED",
  "createdAt": "2026-06-30T22:48:10Z"
}
```

---

### 3. AI Copilot Prompt (`/api/v1/copilot`)

#### `POST /api/v1/copilot/chat`
* **Purpose:** Submit a query regarding case evidence to the AI assistant.
* **Request Payload:**
```json
{
  "caseId": "e0e24dd3-1a22-4467-bc18-97c3bb83b0f5",
  "prompt": "Find persistence indicators on PROD-APP-01",
  "contextEntities": [
    { "type": "host", "value": "PROD-APP-01" }
  ]
}
```
* **Response (200 OK):**
```json
{
  "answer": "I found 2 persistence mechanisms on PROD-APP-01:\n1. A registry Run key pointing to C:\\Windows\\Temp\\updater.exe\n2. A scheduled task named 'WinUpdateHelper' running every day at 12:00 PM.",
  "confidenceScore": 0.94,
  "sources": [
    { "type": "registry", "id": "reg-9923" },
    { "type": "scheduled_task", "id": "task-4829" }
  ]
}
```

---

## 📡 WebSockets Specifications (`/api/v1/ws`)

A persistent bi-directional connection is maintained for real-time progress updates, terminal streaming, and alert flags.

### 1. Connection URL
`ws://<backend_host>/api/v1/ws?token=<jwt_token>`

### 2. Output Message Format (Server -> Client)
Sent when background Celery task stages complete.
```json
{
  "event": "TASK_PROGRESS",
  "data": {
    "taskId": "celery-uuid-98421",
    "caseId": "e0e24dd3-1a22-4467-bc18-97c3bb83b0f5",
    "evidenceId": "2bfb44cf-d54e-4f01-8b27-512a149b5c32",
    "engine": "VOLATILITY_MEM_ANALYSIS",
    "percentageComplete": 85.0,
    "status": "PROCESSING",
    "currentAction": "Running windows.malfind plugin"
  }
}
```

---

## 🕸️ GraphQL Correlation Queries

Utilized to query highly nested structures inside the Neo4j Graph database, resolving multi-hop execution relationships.

### Query Template
```graphql
query GetAttackPath($caseId: ID!, $startNode: String!) {
  case(id: $caseId) {
    correlationPath(start: $startNode, maxDepth: 4) {
      nodes {
        id
        label
        properties {
          key
          value
        }
      }
      edges {
        source
        target
        relationType
      }
    }
  }
}
```
* **Yields:** A sequence of connected nodes and relationships (e.g., File -> spawns -> Process -> network connects -> IP), which is directly parsed by **React Flow** to generate visual graphs.
