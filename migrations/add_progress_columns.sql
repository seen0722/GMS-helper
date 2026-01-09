-- Add progress tracking columns to test_runs table
ALTER TABLE test_runs ADD COLUMN total_clusters INTEGER DEFAULT 0;
ALTER TABLE test_runs ADD COLUMN completed_clusters INTEGER DEFAULT 0;
