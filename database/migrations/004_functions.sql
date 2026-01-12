-- ============================================================================
-- unitMail Database Functions
-- Migration: 004_functions.sql
-- Description: Supabase functions for full-text search and queue management
-- ============================================================================

-- ============================================================================
-- FULL-TEXT SEARCH FUNCTIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Search messages by text query
-- Searches subject, body, from_addr, and to_addr fields
-- Returns messages ranked by relevance
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_messages(
    search_query TEXT,
    folder_filter UUID DEFAULT NULL,
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    message_id VARCHAR,
    folder UUID,
    from_addr VARCHAR,
    to_addr TEXT[],
    subject TEXT,
    body_preview TEXT,
    received_at TIMESTAMPTZ,
    flags JSONB,
    encrypted BOOLEAN,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.message_id,
        m.folder,
        m.from_addr,
        m.to_addr,
        m.subject,
        LEFT(m.body, 200) AS body_preview,
        m.received_at,
        m.flags,
        m.encrypted,
        ts_rank(
            to_tsvector('english', COALESCE(m.subject, '') || ' ' || COALESCE(m.body, '')),
            plainto_tsquery('english', search_query)
        ) AS rank
    FROM messages m
    WHERE
        m.user_id = auth.uid()
        AND (folder_filter IS NULL OR m.folder = folder_filter)
        AND (
            to_tsvector('english', COALESCE(m.subject, '') || ' ' || COALESCE(m.body, ''))
            @@ plainto_tsquery('english', search_query)
            OR m.from_addr ILIKE '%' || search_query || '%'
            OR EXISTS (
                SELECT 1 FROM unnest(m.to_addr) AS addr
                WHERE addr ILIKE '%' || search_query || '%'
            )
        )
    ORDER BY rank DESC, m.received_at DESC
    LIMIT limit_count
    OFFSET offset_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION search_messages IS 'Full-text search on messages with relevance ranking';

-- ----------------------------------------------------------------------------
-- Advanced search with multiple filters
-- Supports date ranges, read status, starred, encrypted filters
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_messages_advanced(
    search_query TEXT DEFAULT NULL,
    folder_filter UUID DEFAULT NULL,
    from_filter TEXT DEFAULT NULL,
    to_filter TEXT DEFAULT NULL,
    date_from TIMESTAMPTZ DEFAULT NULL,
    date_to TIMESTAMPTZ DEFAULT NULL,
    is_read BOOLEAN DEFAULT NULL,
    is_starred BOOLEAN DEFAULT NULL,
    is_encrypted BOOLEAN DEFAULT NULL,
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    message_id VARCHAR,
    folder UUID,
    from_addr VARCHAR,
    to_addr TEXT[],
    subject TEXT,
    body_preview TEXT,
    received_at TIMESTAMPTZ,
    flags JSONB,
    encrypted BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.message_id,
        m.folder,
        m.from_addr,
        m.to_addr,
        m.subject,
        LEFT(m.body, 200) AS body_preview,
        m.received_at,
        m.flags,
        m.encrypted
    FROM messages m
    WHERE
        m.user_id = auth.uid()
        AND (folder_filter IS NULL OR m.folder = folder_filter)
        AND (from_filter IS NULL OR m.from_addr ILIKE '%' || from_filter || '%')
        AND (to_filter IS NULL OR EXISTS (
            SELECT 1 FROM unnest(m.to_addr) AS addr
            WHERE addr ILIKE '%' || to_filter || '%'
        ))
        AND (date_from IS NULL OR m.received_at >= date_from)
        AND (date_to IS NULL OR m.received_at <= date_to)
        AND (is_read IS NULL OR (m.flags->>'read')::BOOLEAN = is_read)
        AND (is_starred IS NULL OR (m.flags->>'starred')::BOOLEAN = is_starred)
        AND (is_encrypted IS NULL OR m.encrypted = is_encrypted)
        AND (search_query IS NULL OR
            to_tsvector('english', COALESCE(m.subject, '') || ' ' || COALESCE(m.body, ''))
            @@ plainto_tsquery('english', search_query)
        )
    ORDER BY m.received_at DESC
    LIMIT limit_count
    OFFSET offset_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION search_messages_advanced IS 'Advanced message search with multiple filter options';

-- ============================================================================
-- QUEUE MANAGEMENT FUNCTIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Get next message from queue for processing
-- Uses FOR UPDATE SKIP LOCKED for concurrent worker safety
-- Returns and locks the next pending message
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_get_next()
RETURNS TABLE (
    id UUID,
    message_id UUID,
    user_id UUID,
    to_addr VARCHAR,
    attempts INTEGER,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    queue_item RECORD;
BEGIN
    -- Select and lock the next pending item
    SELECT q.* INTO queue_item
    FROM queue q
    WHERE q.status = 'pending'
    ORDER BY q.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    -- If found, update status to processing
    IF FOUND THEN
        UPDATE queue
        SET status = 'processing',
            last_attempt = NOW()
        WHERE queue.id = queue_item.id;

        RETURN QUERY
        SELECT
            queue_item.id,
            queue_item.message_id,
            queue_item.user_id,
            queue_item.to_addr,
            queue_item.attempts,
            queue_item.created_at;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_get_next IS 'Atomically fetch and lock the next pending queue item for processing';

-- ----------------------------------------------------------------------------
-- Get multiple items from queue for batch processing
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_get_batch(batch_size INTEGER DEFAULT 10)
RETURNS TABLE (
    id UUID,
    message_id UUID,
    user_id UUID,
    to_addr VARCHAR,
    attempts INTEGER,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH selected AS (
        SELECT q.id
        FROM queue q
        WHERE q.status = 'pending'
        ORDER BY q.created_at ASC
        LIMIT batch_size
        FOR UPDATE SKIP LOCKED
    ),
    updated AS (
        UPDATE queue
        SET status = 'processing',
            last_attempt = NOW()
        WHERE queue.id IN (SELECT selected.id FROM selected)
        RETURNING queue.*
    )
    SELECT
        updated.id,
        updated.message_id,
        updated.user_id,
        updated.to_addr,
        updated.attempts,
        updated.created_at
    FROM updated;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_get_batch IS 'Atomically fetch and lock multiple pending queue items for batch processing';

-- ----------------------------------------------------------------------------
-- Mark queue item as successfully sent
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_mark_complete(queue_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    UPDATE queue
    SET status = 'sent',
        last_attempt = NOW()
    WHERE id = queue_id
    AND status = 'processing';

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_mark_complete IS 'Mark a queue item as successfully sent';

-- ----------------------------------------------------------------------------
-- Mark queue item as failed with error message
-- Implements retry logic with exponential backoff
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_mark_failed(
    queue_id UUID,
    error_msg TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    rows_affected INTEGER;
    current_attempts INTEGER;
    max_attempts CONSTANT INTEGER := 5;
BEGIN
    -- Get current attempts
    SELECT attempts INTO current_attempts
    FROM queue
    WHERE id = queue_id;

    -- Update based on attempt count
    IF current_attempts >= max_attempts THEN
        -- Max attempts reached, mark as permanently failed
        UPDATE queue
        SET status = 'failed',
            error_message = error_msg,
            last_attempt = NOW(),
            attempts = attempts + 1
        WHERE id = queue_id
        AND status = 'processing';
    ELSE
        -- Defer for retry
        UPDATE queue
        SET status = 'deferred',
            error_message = error_msg,
            last_attempt = NOW(),
            attempts = attempts + 1
        WHERE id = queue_id
        AND status = 'processing';
    END IF;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_mark_failed IS 'Mark a queue item as failed with optional retry';

-- ----------------------------------------------------------------------------
-- Requeue deferred items that are ready for retry
-- Uses exponential backoff: 1min, 5min, 15min, 30min, 1hr
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_requeue_deferred()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    UPDATE queue
    SET status = 'pending'
    WHERE status = 'deferred'
    AND last_attempt < NOW() - (
        CASE attempts
            WHEN 1 THEN INTERVAL '1 minute'
            WHEN 2 THEN INTERVAL '5 minutes'
            WHEN 3 THEN INTERVAL '15 minutes'
            WHEN 4 THEN INTERVAL '30 minutes'
            ELSE INTERVAL '1 hour'
        END
    );

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_requeue_deferred IS 'Move deferred items back to pending based on exponential backoff';

-- ----------------------------------------------------------------------------
-- Get queue statistics for monitoring
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION queue_get_stats()
RETURNS TABLE (
    status queue_status,
    count BIGINT,
    oldest TIMESTAMPTZ,
    newest TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.status,
        COUNT(*) AS count,
        MIN(q.created_at) AS oldest,
        MAX(q.created_at) AS newest
    FROM queue q
    GROUP BY q.status
    ORDER BY q.status;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION queue_get_stats IS 'Get queue statistics grouped by status';

-- ============================================================================
-- USER HELPER FUNCTIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Create default system folders for a new user
-- Called after user registration
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION create_default_folders(new_user_id UUID)
RETURNS VOID AS $$
BEGIN
    INSERT INTO folders (user_id, name, is_system) VALUES
        (new_user_id, 'Inbox', true),
        (new_user_id, 'Sent', true),
        (new_user_id, 'Drafts', true),
        (new_user_id, 'Trash', true),
        (new_user_id, 'Spam', true),
        (new_user_id, 'Archive', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION create_default_folders IS 'Create default system folders for a new user';

-- ----------------------------------------------------------------------------
-- Get folder by name for current user
-- Useful for getting system folder IDs
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_folder_by_name(folder_name TEXT)
RETURNS UUID AS $$
DECLARE
    folder_id UUID;
BEGIN
    SELECT id INTO folder_id
    FROM folders
    WHERE user_id = auth.uid()
    AND name = folder_name;

    RETURN folder_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_folder_by_name IS 'Get folder ID by name for the current user';

-- ----------------------------------------------------------------------------
-- Get unread message count per folder
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_unread_counts()
RETURNS TABLE (
    folder_id UUID,
    folder_name VARCHAR,
    unread_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id AS folder_id,
        f.name::VARCHAR AS folder_name,
        COUNT(m.id) FILTER (WHERE (m.flags->>'read')::BOOLEAN = false) AS unread_count
    FROM folders f
    LEFT JOIN messages m ON m.folder = f.id AND m.user_id = auth.uid()
    WHERE f.user_id = auth.uid()
    GROUP BY f.id, f.name
    ORDER BY f.is_system DESC, f.name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_unread_counts IS 'Get unread message count for each folder';

-- ============================================================================
-- TRIGGER: Auto-create folders for new users
-- ============================================================================
CREATE OR REPLACE FUNCTION on_user_created()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM create_default_folders(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER users_after_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION on_user_created();

-- ============================================================================
-- CLEANUP FUNCTIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Permanently delete messages in trash older than specified days
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION cleanup_trash(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
    trash_folder_id UUID;
BEGIN
    -- Get trash folder ID for the current user
    SELECT id INTO trash_folder_id
    FROM folders
    WHERE user_id = auth.uid()
    AND name = 'Trash'
    AND is_system = true;

    IF trash_folder_id IS NULL THEN
        RETURN 0;
    END IF;

    DELETE FROM messages
    WHERE user_id = auth.uid()
    AND folder = trash_folder_id
    AND received_at < NOW() - (days_old || ' days')::INTERVAL;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_trash IS 'Delete messages in trash older than specified days';

-- ----------------------------------------------------------------------------
-- Clean up old sent queue items
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION cleanup_queue(days_old INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM queue
    WHERE status = 'sent'
    AND created_at < NOW() - (days_old || ' days')::INTERVAL;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_queue IS 'Delete completed queue items older than specified days';
