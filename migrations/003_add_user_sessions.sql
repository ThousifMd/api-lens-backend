-- Migration: Add user_sessions table for session tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    client_user_id UUID NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    country VARCHAR(3),
    region VARCHAR(100),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(company_id, client_user_id, session_id)
); 