-- Migration: 005_complete_missing_schema.sql
-- Description: Ensures properties, property_chunks, and all required columns exist safely.

-- 1. Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Ensure 'users' has 'dealer_id' column
ALTER TABLE users ADD COLUMN IF NOT EXISTS dealer_id UUID DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_dealer_id_unique ON users(dealer_id);

-- 3. Ensure 'refresh_tokens' has 'client_id' and 'last_used_at'
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS client_id VARCHAR(255) DEFAULT 'web-client';
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ DEFAULT NOW();

-- 4. Create 'properties' table (plural, expected by backend API)
CREATE TABLE IF NOT EXISTS properties (
    property_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dealer_id UUID NOT NULL,
    name TEXT NOT NULL,
    aliases TEXT[] DEFAULT '{}',
    city TEXT NOT NULL,
    region TEXT,
    property_type TEXT NOT NULL,
    unit_types JSONB NOT NULL DEFAULT '[]',
    facts JSONB NOT NULL DEFAULT '{}',
    raw_text TEXT,
    cleaned_text TEXT,
    extraction_warnings JSONB DEFAULT '[]',
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_dealer_id ON properties(dealer_id);

-- 5. Create 'property_chunks' table (pgvector embeddings for AI caller)
CREATE TABLE IF NOT EXISTS property_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(property_id) ON DELETE CASCADE,
    dealer_id UUID NOT NULL,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_property_chunks_dealer_id ON property_chunks(dealer_id);
CREATE INDEX IF NOT EXISTS idx_property_chunks_embedding 
    ON property_chunks USING hnsw (embedding vector_cosine_ops);

-- 6. Ensure 'calls' has all required columns
ALTER TABLE calls ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS to_phone_number VARCHAR(50);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS direction VARCHAR(20);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS flow_name VARCHAR(100);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS outcome VARCHAR(250);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS call_sid VARCHAR(100);

-- 7. Ensure 'leads' has all required columns
ALTER TABLE leads ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'New';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS interest VARCHAR(100) DEFAULT 'Premium Plot';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS current_attempt INT DEFAULT 0;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS follow_up_status VARCHAR(100) DEFAULT 'Pending First Call';
