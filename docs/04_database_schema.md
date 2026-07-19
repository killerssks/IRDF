# 04. Database Schema Specifications

This document outlines the design and schema definitions for the multi-database persistence layers used in the **AI-DFIR Platform**. It specifies PostgreSQL tables, Neo4j Graph relations, and Qdrant Vector collections.

---

## 🏛️ Relational Entity-Relationship Model (PostgreSQL)

The relational engine stores structured tables, system authentication configurations, case tracking metrics, and evidence chains of custody.

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        boolean is_active
        timestamp created_at
    }
    ROLES {
        uuid id PK
        string role_name UK
        string permissions
    }
    USER_ROLES {
        uuid user_id FK
        uuid role_id FK
    }
    CASES {
        uuid id PK
        string name
        string severity
        string status
        uuid owner_id FK
        timestamp created_at
        timestamp updated_at
    }
    EVIDENCE {
        uuid id PK
        uuid case_id FK
        string file_name
        string storage_path
        string sha256_hash
        string md5_hash
        string status
        bigint file_size
        timestamp created_at
    }
    CHAIN_OF_CUSTODY {
        uuid id PK
        uuid evidence_id FK
        uuid action_by FK
        string action_taken
        string source_location
        string dest_location
        string notes
        timestamp action_timestamp
        string integrity_signature
    }
    NOTES {
        uuid id PK
        uuid case_id FK
        uuid author_id FK
        text content
        timestamp created_at
    }

    USERS ||--o{ USER_ROLES : has
    ROLES ||--o{ USER_ROLES : contains
    USERS ||--o{ CASES : manages
    CASES ||--o{ EVIDENCE : holds
    EVIDENCE ||--o{ CHAIN_OF_CUSTODY : tracks
    CASES ||--o{ NOTES : logs
    USERS ||--o{ NOTES : writes
```

---

## 🕸️ Graph Database Schema (Neo4j)

The graph database processes security event relationships. Nodes correspond to entities, and edges represent activities.

### Nodes (Labels & Properties)
* **`Host`**: `id` (Hostname/UUID), `ip_address`, `os_type`, `domain`.
* **`Process`**: `id` (PID + host), `pid`, `name`, `path`, `command_line`, `sha256`.
* **`File`**: `path`, `name`, `sha256`, `md5`, `size`, `entropy`.
* **`IPAddress`**: `ip`, `country`, `asn`, `reputation_score`.
* **`Domain`**: `domain_name`, `registrar`, `creation_date`.
* **`RegistryKey`**: `key_path`, `value_name`, `value_data`.
* **`User`**: `username`, `domain`, `privileges`.

### Relationships (Edges)
* `(Process)-[:SPAWNED]->(Process)`
* `(Process)-[:WROTE]->(File)`
* `(Process)-[:READ]->(File)`
* `(Process)-[:OPENED_SOCKET]->(IPAddress)`
* `(Process)-[:MODIFIED_REGISTRY]->(RegistryKey)`
* `(Host)-[:LOGGED_IN_USER]->(User)`
* `(File)-[:RESOLVES_TO]->(Domain)`

```mermaid
graph TD
    User((User)) -- LOGGED_IN_USER --> Host((Host))
    Host -- RUNNING_PROCESS --> Process((Process))
    Process -- SPAWNED --> ChildProcess((Process))
    Process -- WROTE --> File((File))
    Process -- OPENED_SOCKET --> IPAddress((IPAddress))
    Process -- MODIFIED_REGISTRY --> RegistryKey((RegistryKey))
    IPAddress -- RESOLVES_TO --> Domain((Domain))
```

---

## 🧠 Vector Database Schema (Qdrant / Chroma)

The vector search database stores high-dimensional embeddings of text, decompiled code instructions, event descriptions, and intelligence feeds.

### Collection 1: `forensic_timelines`
* **Vector Configuration:** 1536 Dimensions (for standard `text-embedding-3-small` / OpenAI compatibility) or 1024 Dimensions (`bge-large-en-v1.5` for local embeddings).
* **Distance Metric:** Cosine Similarity.
* **Payload Fields:**
  * `case_id`: UUID
  * `timestamp`: Unix timestamp
  * `event_type`: "process" | "network" | "registry" | "file"
  * `raw_log`: String of original event output
  * `summary`: String explanation generated during indexing

### Collection 2: `reverse_engineering_symbols`
* **Vector Configuration:** 768 Dimensions (using models like `codebert-base` or `graphcodebert`).
* **Distance Metric:** Cosine / Inner Product.
* **Payload Fields:**
  * `file_sha256`: String
  * `function_name`: String
  * `assembly_code`: Text string
  * `decompiled_pseudocode`: Text string
  * `predicted_capability`: Array of strings (e.g. `["crypto", "socket"]`)

### Collection 3: `threat_intelligence_reports`
* **Vector Configuration:** 1536 Dimensions (or equivalent).
* **Distance Metric:** Cosine.
* **Payload Fields:**
  * `threat_actor`: String (e.g., "APT29")
  * `indicators`: Array of strings
  * `mitre_techniques`: Array of strings
  * `source_url`: String
  * `parsed_document`: Markdown text snippet
