-- postgres_schema.sql
-- Relational Database Schema for AI-DFIR Platform Core Data

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Define Enums
CREATE TYPE case_status AS ENUM ('OPEN', 'IN_INVESTIGATION', 'CONTAINED', 'RESOLVED', 'CLOSED');
CREATE TYPE case_severity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE case_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE evidence_status AS ENUM ('QUEUED', 'PROCESSING', 'READY', 'ERROR', 'ARCHIVED');
CREATE TYPE evidence_type AS ENUM ('DISK', 'MEM', 'PCAP', 'LOG', 'BINARY', 'GENERIC');
CREATE TYPE coc_action AS ENUM ('INGEST', 'CHECKOUT', 'CHECKIN', 'EXTRACT_SUB_ARTIFACT', 'ARCHIVE', 'DELETE_ATTEMPT');

-- 1. Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Roles Table
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_name VARCHAR(100) NOT NULL UNIQUE,
    permissions JSONB NOT NULL, -- Array of string permission nodes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. User Roles Join Table
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- 4. Cases Table
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    status case_status DEFAULT 'OPEN',
    severity case_severity DEFAULT 'MEDIUM',
    priority case_priority DEFAULT 'MEDIUM',
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    department VARCHAR(255),
    tags VARCHAR(100)[],
    sla_deadline TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Evidence Table
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    md5_hash CHAR(32) NOT NULL,
    ssdeep_hash VARCHAR(255),
    status evidence_status DEFAULT 'QUEUED',
    file_size BIGINT NOT NULL,
    evidence_type evidence_type NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb, -- Store parsed metadata (e.g. disk partitions)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Chain of Custody Table (Append-Only)
CREATE TABLE chain_of_custody (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evidence_id UUID REFERENCES evidence(id) ON DELETE RESTRICT,
    action_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    action_taken coc_action NOT NULL,
    source_location VARCHAR(512) NOT NULL,
    dest_location VARCHAR(512) NOT NULL,
    notes TEXT,
    action_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    integrity_signature VARCHAR(512) NOT NULL, -- Digital signature signed by user certificate
    previous_row_hash CHAR(64) -- Linkage for audit chain verifications
);

-- 7. Case Notes Table
CREATE TABLE case_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Bookmarks / Marked Artifacts Table
CREATE TABLE forensic_bookmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    artifact_ref VARCHAR(255) NOT NULL, -- e.g., "registry:SYSTEM:Run"
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Querying
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_evidence_case_id ON evidence(case_id);
CREATE INDEX idx_evidence_sha256 ON evidence(sha256_hash);
CREATE INDEX idx_coc_evidence_id ON chain_of_custody(evidence_id);
CREATE INDEX idx_case_notes_case_id ON case_notes(case_id);

-- Enforce CoC Append-Only Rules via DB Triggers
CREATE OR REPLACE FUNCTION prevent_coc_updates() 
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Updates or Deletes on Chain of Custody logs are strictly forbidden for compliance integrity.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER coc_no_update_delete
BEFORE UPDATE OR DELETE ON chain_of_custody
FOR EACH ROW EXECUTE FUNCTION prevent_coc_updates();
