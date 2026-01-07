-- Migration: Add LLM Provider Settings
-- Date: 2026-01-07
-- Description: Add columns to settings table for internal LLM (Ollama/vLLM) support

ALTER TABLE settings ADD COLUMN llm_provider VARCHAR(20) DEFAULT 'openai';
ALTER TABLE settings ADD COLUMN internal_llm_url VARCHAR(255);
ALTER TABLE settings ADD COLUMN internal_llm_model VARCHAR(50) DEFAULT 'llama3.1:8b';
