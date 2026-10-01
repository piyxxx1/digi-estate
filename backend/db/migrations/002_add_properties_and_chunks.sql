-- Enable pgvector if not already present
CREATE EXTENSION IF NOT EXISTS vector;

-- Properties table
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

-- Property chunks table
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
CREATE INDEX IF NOT EXISTS idx_property_chunks_embedding ON property_chunks USING hnsw (embedding vector_cosine_ops);
