# 09. Security & Compliance Specifications

This document outlines the security controls, access models, audit logging definitions, and key management frameworks configured to guarantee compliance and evidence integrity inside the **AI-DFIR Platform**.

---

## 🔐 Role-Based Access Control (RBAC)

The system implements a granular access matrix based on roles assigned during authentication (OIDC / OAuth2 with SSO integration).

| Resource / Action | Admin | Lead Investigator | Analyst | External Auditor |
|---|---|---|---|---|
| **Create/Delete Case** | Yes | Yes | No | No |
| **Ingest Evidence** | Yes | Yes | Yes | No |
| **Download Raw Evidence** | Yes | Yes (Audited) | No | No |
| **View Forensic Dashboard**| Yes | Yes | Yes | Yes |
| **Write Notes / Comments** | Yes | Yes | Yes | No |
| **Query AI Copilot** | Yes | Yes | Yes | Yes (View Only) |
| **Export Case Reports** | Yes | Yes | Yes | Yes |
| **Configure System KMS** | Yes | No | No | No |
| **Access Audit Logs** | Yes | Yes | No | Yes |

---

## 📝 Audit Log Specification (RFC 5424)

All user transactions, API calls, and workspace actions generate an immutable log record exported to a centralized, write-once index.

### Log Entry Schema
Every log entry utilizes a strict JSON structure following RFC 5424 formatting:

```json
{
  "syslogHeader": {
    "pri": 14,
    "version": 1,
    "timestamp": "2026-06-30T22:58:12.443Z",
    "hostname": "dfir-gateway-01",
    "appName": "dfir-auth-service",
    "procId": "12983",
    "msgId": "AUTH_LOGIN_SUCCESS"
  },
  "structuredData": {
    "session": {
      "sessionId": "sess_894317283",
      "userId": "usr_9984e2a3",
      "userEmail": "analyst.smith@enterprise.com",
      "userRole": "ANALYST",
      "clientIp": "192.168.42.115"
    },
    "action": {
      "category": "EVIDENCE_ACCESS",
      "type": "DOWNLOAD_ATTEMPT",
      "targetId": "ev_2bfb44cf",
      "targetHash": "8f4384a51e604f3261a86845347fa65e90403e0a137ca25dbcb41e17ca26262b",
      "status": "APPROVED"
    }
  },
  "signatureBlock": {
    "hashAlg": "SHA256",
    "signatureValue": "MEQCIFz52u4qW...signed_hash_representing_row_integrity..."
  }
}
```

### Integrity Controls
* **WORM Log Pipelines:** Logs are immediately shipped via Logstash/Fluentd to a read-only Elasticsearch container with index lifecycle policies that prevent any deletion operations.
* **Hash Chaining:** Each log entry incorporates a `signatureBlock` referencing the SHA-256 of the prior log entry, forming a cryptographic chain that detects database tampering.

---

## 🔑 Key Management System (KMS) & Encryption

To protect evidence confidentiality, all files at rest and data in transit are encrypted using industry-standard primitives.

```
+---------------------------------------------------------------------------------+
|                                 HASHICORP VAULT                                 |
|                                                                                 |
|   +--------------------------+             +--------------------------------+   |
|   |   Root Key (HSM Backed)  | ----------> |   Key Encryption Key (KEK)     |   |
|   +--------------------------+             +--------------------------------+   |
+---------------------------------------------------------------------------------+
                                                             |
                                                             | (Unwraps)
                                                             v
                                             +--------------------------------+
                                             |   Data Encryption Key (DEK)    |
                                             +--------------------------------+
                                                             |
                                                             | (Encrypts)
                                                             v
                                             +--------------------------------+
                                             |   Raw Evidence File on MinIO   |
                                             +--------------------------------+
```

### Encryption Protocols
* **Data in Transit:** Enforced TLS 1.3 across all internal and external communication ports. Cryptographic ciphers are limited to:
  * `TLS_AES_256_GCM_SHA384`
  * `TLS_CHACHA20_POLY1305_SHA256`
* **Data at Rest:**
  * **Relational DB:** PostgreSQL Table Space Encryption (TDE).
  * **Object Storage:** Envelope Encryption. MinIO queries HashiCorp Vault to unwrap a Data Encryption Key (DEK) dynamically on file read. The actual files stored in MinIO blocks are AES-256-GCM ciphertexts.
  * **Encryption Key Rotation:** Key Encryption Keys (KEKs) are rotated automatically every 90 days. Old keys are archived securely to allow decryption of older historical archives.
