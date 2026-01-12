-- ============================================================================
-- unitMail Row Level Security Policies
-- Migration: 003_rls_policies.sql
-- Description: Implements multi-tenant isolation using Supabase RLS
-- ============================================================================

-- ============================================================================
-- ENABLE ROW LEVEL SECURITY ON ALL TABLES
-- ============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE config ENABLE ROW LEVEL SECURITY;
ALTER TABLE mesh_peers ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- HELPER FUNCTION: Get current authenticated user ID
-- Uses Supabase's auth.uid() function
-- ============================================================================

-- Note: auth.uid() is provided by Supabase and returns the authenticated user's ID
-- This wrapper allows for easier testing and potential customization
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- USERS TABLE POLICIES
-- Users can only view and update their own profile
-- ============================================================================

-- Users can view their own profile
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (id = auth.uid());

-- Users can update their own profile
CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Users cannot delete their own account directly (use admin function)
-- No DELETE policy = denied by default

-- Insert is handled by Supabase Auth, not direct table access
-- No INSERT policy for regular users

-- ============================================================================
-- FOLDERS TABLE POLICIES
-- Users can only access their own folders
-- ============================================================================

-- Users can view their own folders
CREATE POLICY folders_select_own ON folders
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create folders for themselves
CREATE POLICY folders_insert_own ON folders
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own non-system folders
CREATE POLICY folders_update_own ON folders
    FOR UPDATE
    USING (user_id = auth.uid() AND is_system = false)
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own non-system folders
CREATE POLICY folders_delete_own ON folders
    FOR DELETE
    USING (user_id = auth.uid() AND is_system = false);

-- ============================================================================
-- MESSAGES TABLE POLICIES
-- Users can only access their own messages
-- ============================================================================

-- Users can view their own messages
CREATE POLICY messages_select_own ON messages
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create messages for themselves
CREATE POLICY messages_insert_own ON messages
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own messages (flags, folder, etc.)
CREATE POLICY messages_update_own ON messages
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own messages
CREATE POLICY messages_delete_own ON messages
    FOR DELETE
    USING (user_id = auth.uid());

-- ============================================================================
-- CONTACTS TABLE POLICIES
-- Users can only access their own contacts
-- ============================================================================

-- Users can view their own contacts
CREATE POLICY contacts_select_own ON contacts
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create contacts for themselves
CREATE POLICY contacts_insert_own ON contacts
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own contacts
CREATE POLICY contacts_update_own ON contacts
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own contacts
CREATE POLICY contacts_delete_own ON contacts
    FOR DELETE
    USING (user_id = auth.uid());

-- ============================================================================
-- QUEUE TABLE POLICIES
-- Users can view their own queue items, system handles processing
-- ============================================================================

-- Users can view their own queue items
CREATE POLICY queue_select_own ON queue
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create queue items for themselves (sending emails)
CREATE POLICY queue_insert_own ON queue
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users cannot directly update or delete queue items
-- Queue management is handled by backend service functions

-- Service role policy for queue processing (backend workers)
CREATE POLICY queue_service_all ON queue
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- CONFIG TABLE POLICIES
-- Users can only access their own configuration
-- ============================================================================

-- Users can view their own config
CREATE POLICY config_select_own ON config
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create config entries for themselves
CREATE POLICY config_insert_own ON config
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own config
CREATE POLICY config_update_own ON config
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own config entries
CREATE POLICY config_delete_own ON config
    FOR DELETE
    USING (user_id = auth.uid());

-- ============================================================================
-- MESH_PEERS TABLE POLICIES
-- Users can manage their own mesh network peers
-- ============================================================================

-- Users can view their own mesh peers
CREATE POLICY mesh_peers_select_own ON mesh_peers
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can create mesh peers for themselves
CREATE POLICY mesh_peers_insert_own ON mesh_peers
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own mesh peers
CREATE POLICY mesh_peers_update_own ON mesh_peers
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own mesh peers
CREATE POLICY mesh_peers_delete_own ON mesh_peers
    FOR DELETE
    USING (user_id = auth.uid());

-- ============================================================================
-- SERVICE ROLE BYPASS POLICIES
-- Allow service role full access for backend operations
-- ============================================================================

-- Service role can access all users (for admin operations)
CREATE POLICY users_service_all ON users
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Service role can access all messages (for SMTP gateway)
CREATE POLICY messages_service_all ON messages
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Service role can access all folders (for system folder creation)
CREATE POLICY folders_service_all ON folders
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Service role can access all contacts (for import/export)
CREATE POLICY contacts_service_all ON contacts
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Service role can access all config (for system settings)
CREATE POLICY config_service_all ON config
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Service role can access all mesh peers (for mesh management)
CREATE POLICY mesh_peers_service_all ON mesh_peers
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
