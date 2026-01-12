-- ============================================================================
-- unitMail Test Data Seed
-- Seed: 001_test_data.sql
-- Description: Sample data for development and testing environments
-- ============================================================================
--
-- This seed file creates sample data including:
-- - Test users with different roles
-- - System and custom folders for each user
-- - Sample email messages (inbox, sent, drafts)
-- - Contact entries
-- - Queue items for outbound messages
-- - Mesh peer configurations
--
-- WARNING: This data is for development/testing only!
-- Do NOT run this on production databases.
--
-- Usage:
--   psql -d unitmail -f database/seeds/001_test_data.sql
--   or via Supabase SQL editor
-- ============================================================================

-- ============================================================================
-- CLEANUP: Remove existing test data (for re-seeding)
-- ============================================================================
-- Delete in correct order to respect foreign key constraints

DELETE FROM queue WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM messages WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM contacts WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM config WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM mesh_peers WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM folders WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@test.unitmail.local'
);

DELETE FROM users WHERE email LIKE '%@test.unitmail.local';


-- ============================================================================
-- USERS: Test accounts
-- ============================================================================
-- Password for all test users: "testpass123" (bcrypt hash)
-- In real usage, generate proper hashes with: SELECT crypt('password', gen_salt('bf'));

INSERT INTO users (id, email, password_hash, name, created_at, updated_at)
VALUES
    -- Primary test user
    (
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'alice@test.unitmail.local',
        '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.OPQQqrFUkDZVWi',
        'Alice Johnson',
        NOW() - INTERVAL '30 days',
        NOW() - INTERVAL '1 day'
    ),
    -- Secondary test user
    (
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'bob@test.unitmail.local',
        '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.OPQQqrFUkDZVWi',
        'Bob Smith',
        NOW() - INTERVAL '25 days',
        NOW() - INTERVAL '2 days'
    ),
    -- Admin test user
    (
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'admin@test.unitmail.local',
        '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.OPQQqrFUkDZVWi',
        'System Admin',
        NOW() - INTERVAL '60 days',
        NOW()
    );


-- ============================================================================
-- FOLDERS: System and custom folders for each user
-- ============================================================================

-- Alice's folders
INSERT INTO folders (id, user_id, name, parent_id, is_system, created_at)
VALUES
    -- System folders
    (
        'f0001001-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Inbox',
        NULL,
        TRUE,
        NOW() - INTERVAL '30 days'
    ),
    (
        'f0001002-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Sent',
        NULL,
        TRUE,
        NOW() - INTERVAL '30 days'
    ),
    (
        'f0001003-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Drafts',
        NULL,
        TRUE,
        NOW() - INTERVAL '30 days'
    ),
    (
        'f0001004-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Trash',
        NULL,
        TRUE,
        NOW() - INTERVAL '30 days'
    ),
    (
        'f0001005-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Spam',
        NULL,
        TRUE,
        NOW() - INTERVAL '30 days'
    ),
    -- Custom folders
    (
        'f0001006-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Work',
        NULL,
        FALSE,
        NOW() - INTERVAL '20 days'
    ),
    (
        'f0001007-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Personal',
        NULL,
        FALSE,
        NOW() - INTERVAL '20 days'
    );

-- Bob's folders (system only)
INSERT INTO folders (id, user_id, name, parent_id, is_system, created_at)
VALUES
    (
        'f0002001-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Inbox',
        NULL,
        TRUE,
        NOW() - INTERVAL '25 days'
    ),
    (
        'f0002002-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Sent',
        NULL,
        TRUE,
        NOW() - INTERVAL '25 days'
    ),
    (
        'f0002003-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Drafts',
        NULL,
        TRUE,
        NOW() - INTERVAL '25 days'
    ),
    (
        'f0002004-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Trash',
        NULL,
        TRUE,
        NOW() - INTERVAL '25 days'
    );

-- Admin's folders (system only)
INSERT INTO folders (id, user_id, name, parent_id, is_system, created_at)
VALUES
    (
        'f0003001-0000-0000-0000-000000000003',
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'Inbox',
        NULL,
        TRUE,
        NOW() - INTERVAL '60 days'
    ),
    (
        'f0003002-0000-0000-0000-000000000003',
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'Sent',
        NULL,
        TRUE,
        NOW() - INTERVAL '60 days'
    ),
    (
        'f0003003-0000-0000-0000-000000000003',
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'Drafts',
        NULL,
        TRUE,
        NOW() - INTERVAL '60 days'
    ),
    (
        'f0003004-0000-0000-0000-000000000003',
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'Trash',
        NULL,
        TRUE,
        NOW() - INTERVAL '60 days'
    );


-- ============================================================================
-- MESSAGES: Sample emails
-- ============================================================================

-- Alice's inbox messages
INSERT INTO messages (
    id, message_id, user_id, folder, from_addr, to_addr, cc_addr,
    subject, body, body_html, flags, encrypted, created_at, received_at
)
VALUES
    -- Welcome email
    (
        'm0001001-0000-0000-0000-000000000001',
        '<welcome-001@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001001-0000-0000-0000-000000000001',
        'system@test.unitmail.local',
        ARRAY['alice@test.unitmail.local'],
        ARRAY[]::TEXT[],
        'Welcome to unitMail!',
        'Hello Alice,\n\nWelcome to unitMail! We''re excited to have you on board.\n\nunitMail is a secure, privacy-focused email system that puts you in control of your data.\n\nGetting Started:\n- Set up your profile\n- Import your contacts\n- Configure your security settings\n\nIf you have any questions, feel free to reach out.\n\nBest regards,\nThe unitMail Team',
        '<html><body><h1>Welcome to unitMail!</h1><p>Hello Alice,</p><p>Welcome to unitMail! We''re excited to have you on board.</p><p>unitMail is a secure, privacy-focused email system that puts you in control of your data.</p><h2>Getting Started:</h2><ul><li>Set up your profile</li><li>Import your contacts</li><li>Configure your security settings</li></ul><p>If you have any questions, feel free to reach out.</p><p>Best regards,<br>The unitMail Team</p></body></html>',
        '{"read": true, "starred": true, "important": true}',
        FALSE,
        NOW() - INTERVAL '29 days',
        NOW() - INTERVAL '29 days'
    ),
    -- Email from Bob
    (
        'm0001002-0000-0000-0000-000000000001',
        '<msg-002@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001001-0000-0000-0000-000000000001',
        'bob@test.unitmail.local',
        ARRAY['alice@test.unitmail.local'],
        ARRAY[]::TEXT[],
        'Project Update',
        'Hi Alice,\n\nJust wanted to give you a quick update on the project.\n\nWe''ve made good progress this week:\n- Completed the database schema\n- Implemented the API endpoints\n- Started on the frontend\n\nLet me know if you want to sync up tomorrow.\n\nCheers,\nBob',
        NULL,
        '{"read": true, "starred": false, "important": false}',
        FALSE,
        NOW() - INTERVAL '5 days',
        NOW() - INTERVAL '5 days'
    ),
    -- Unread email
    (
        'm0001003-0000-0000-0000-000000000001',
        '<msg-003@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001001-0000-0000-0000-000000000001',
        'newsletter@example.com',
        ARRAY['alice@test.unitmail.local'],
        ARRAY[]::TEXT[],
        'Weekly Tech Newsletter',
        'This week in tech:\n\n1. New encryption standards announced\n2. Privacy regulations update\n3. Open source project highlights\n\nRead more at our website.',
        NULL,
        '{"read": false, "starred": false, "important": false}',
        FALSE,
        NOW() - INTERVAL '1 day',
        NOW() - INTERVAL '1 day'
    ),
    -- Encrypted message
    (
        'm0001004-0000-0000-0000-000000000001',
        '<encrypted-001@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001001-0000-0000-0000-000000000001',
        'secure@external.example.com',
        ARRAY['alice@test.unitmail.local'],
        ARRAY[]::TEXT[],
        'Encrypted: Confidential Information',
        '-----BEGIN PGP MESSAGE-----\nVersion: OpenPGP\n\nhQEMA...encrypted content placeholder...=\n-----END PGP MESSAGE-----',
        NULL,
        '{"read": false, "starred": false, "important": true}',
        TRUE,
        NOW() - INTERVAL '2 hours',
        NOW() - INTERVAL '2 hours'
    );

-- Alice's sent messages
INSERT INTO messages (
    id, message_id, user_id, folder, from_addr, to_addr, cc_addr,
    subject, body, flags, encrypted, created_at, received_at
)
VALUES
    (
        'm0001005-0000-0000-0000-000000000001',
        '<sent-001@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001002-0000-0000-0000-000000000001',
        'alice@test.unitmail.local',
        ARRAY['bob@test.unitmail.local'],
        ARRAY['admin@test.unitmail.local'],
        'Re: Project Update',
        'Hi Bob,\n\nThanks for the update! Great progress.\n\nLet''s sync tomorrow at 2 PM.\n\nAlice',
        '{"read": true, "starred": false, "important": false}',
        FALSE,
        NOW() - INTERVAL '4 days',
        NOW() - INTERVAL '4 days'
    );

-- Alice's draft
INSERT INTO messages (
    id, message_id, user_id, folder, from_addr, to_addr, cc_addr,
    subject, body, flags, encrypted, created_at, received_at
)
VALUES
    (
        'm0001006-0000-0000-0000-000000000001',
        '<draft-001@test.unitmail.local>',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0001003-0000-0000-0000-000000000001',
        'alice@test.unitmail.local',
        ARRAY['team@example.com'],
        ARRAY[]::TEXT[],
        'Meeting Notes - Draft',
        'Meeting notes from today:\n\n- Item 1\n- Item 2\n\n[TODO: Add more details]',
        '{"read": true, "starred": false, "important": false}',
        FALSE,
        NOW() - INTERVAL '3 hours',
        NOW() - INTERVAL '3 hours'
    );

-- Bob's inbox (message from Alice)
INSERT INTO messages (
    id, message_id, user_id, folder, from_addr, to_addr, cc_addr,
    subject, body, flags, encrypted, created_at, received_at
)
VALUES
    (
        'm0002001-0000-0000-0000-000000000002',
        '<sent-001@test.unitmail.local>',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'f0002001-0000-0000-0000-000000000002',
        'alice@test.unitmail.local',
        ARRAY['bob@test.unitmail.local'],
        ARRAY['admin@test.unitmail.local'],
        'Re: Project Update',
        'Hi Bob,\n\nThanks for the update! Great progress.\n\nLet''s sync tomorrow at 2 PM.\n\nAlice',
        '{"read": true, "starred": false, "important": false}',
        FALSE,
        NOW() - INTERVAL '4 days',
        NOW() - INTERVAL '4 days'
    );


-- ============================================================================
-- CONTACTS: Address book entries
-- ============================================================================

-- Alice's contacts
INSERT INTO contacts (id, user_id, name, email, pgp_key, notes, created_at)
VALUES
    (
        'c0001001-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Bob Smith',
        'bob@test.unitmail.local',
        NULL,
        'Colleague - Engineering team',
        NOW() - INTERVAL '28 days'
    ),
    (
        'c0001002-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'System Admin',
        'admin@test.unitmail.local',
        NULL,
        'IT Administrator',
        NOW() - INTERVAL '28 days'
    ),
    (
        'c0001003-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'External Contact',
        'contact@example.com',
        '-----BEGIN PGP PUBLIC KEY BLOCK-----\nVersion: OpenPGP\n\nmQENBF...placeholder public key...=\n-----END PGP PUBLIC KEY BLOCK-----',
        'Has PGP key for encrypted communication',
        NOW() - INTERVAL '15 days'
    ),
    (
        'c0001004-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Marketing Team',
        'marketing@company.example.com',
        NULL,
        'Marketing department mailing list',
        NOW() - INTERVAL '10 days'
    );

-- Bob's contacts
INSERT INTO contacts (id, user_id, name, email, pgp_key, notes, created_at)
VALUES
    (
        'c0002001-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Alice Johnson',
        'alice@test.unitmail.local',
        NULL,
        'Project lead',
        NOW() - INTERVAL '24 days'
    ),
    (
        'c0002002-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'Support Team',
        'support@unitmail.local',
        NULL,
        'Technical support',
        NOW() - INTERVAL '20 days'
    );


-- ============================================================================
-- QUEUE: Outbound email queue items
-- ============================================================================

INSERT INTO queue (
    id, message_id, user_id, to_addr, status, attempts, last_attempt, error_message, created_at
)
VALUES
    -- Pending delivery
    (
        'q0001001-0000-0000-0000-000000000001',
        'm0001005-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'bob@test.unitmail.local',
        'pending',
        0,
        NULL,
        NULL,
        NOW() - INTERVAL '1 minute'
    ),
    -- Processing
    (
        'q0001002-0000-0000-0000-000000000001',
        'm0001005-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'admin@test.unitmail.local',
        'processing',
        1,
        NOW() - INTERVAL '30 seconds',
        NULL,
        NOW() - INTERVAL '2 minutes'
    ),
    -- Deferred (temporary failure)
    (
        'q0001003-0000-0000-0000-000000000001',
        'm0001006-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'external@slow-server.example.com',
        'deferred',
        2,
        NOW() - INTERVAL '5 minutes',
        'Connection timeout - server did not respond',
        NOW() - INTERVAL '30 minutes'
    ),
    -- Failed delivery
    (
        'q0001004-0000-0000-0000-000000000001',
        'm0001006-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'invalid@nonexistent-domain-12345.com',
        'failed',
        3,
        NOW() - INTERVAL '1 hour',
        'DNS resolution failed: NXDOMAIN',
        NOW() - INTERVAL '2 hours'
    );


-- ============================================================================
-- CONFIG: User configuration settings
-- ============================================================================

INSERT INTO config (id, user_id, key, value, updated_at)
VALUES
    -- Alice's config
    (
        'cfg001-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'signature',
        '{"text": "Best regards,\nAlice Johnson\nalice@test.unitmail.local", "html": "<p>Best regards,<br><strong>Alice Johnson</strong><br><a href=\"mailto:alice@test.unitmail.local\">alice@test.unitmail.local</a></p>"}',
        NOW() - INTERVAL '25 days'
    ),
    (
        'cfg002-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'display',
        '{"theme": "light", "density": "comfortable", "show_preview": true, "messages_per_page": 50}',
        NOW() - INTERVAL '20 days'
    ),
    (
        'cfg003-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'notifications',
        '{"email_alerts": true, "desktop_notifications": true, "sound": false}',
        NOW() - INTERVAL '15 days'
    ),
    -- Bob's config
    (
        'cfg001-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'signature',
        '{"text": "Cheers,\nBob", "html": "<p>Cheers,<br>Bob</p>"}',
        NOW() - INTERVAL '20 days'
    ),
    (
        'cfg002-0000-0000-0000-000000000002',
        'b2c3d4e5-f6a7-8901-bcde-f23456789012',
        'display',
        '{"theme": "dark", "density": "compact", "show_preview": false, "messages_per_page": 25}',
        NOW() - INTERVAL '18 days'
    );


-- ============================================================================
-- MESH_PEERS: WireGuard mesh network peers
-- ============================================================================

INSERT INTO mesh_peers (
    id, user_id, name, email_domain, public_key, endpoint, allowed_ips, last_seen, created_at
)
VALUES
    -- Alice's mesh peers
    (
        'mp001-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'Home Server',
        'home.alice.local',
        'WGPubKey1234567890abcdefghijklmnopqrstuv==',
        '192.168.1.100:51820',
        ARRAY['10.0.0.1/32', '192.168.1.0/24'],
        NOW() - INTERVAL '5 minutes',
        NOW() - INTERVAL '20 days'
    ),
    (
        'mp002-0000-0000-0000-000000000001',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'VPS Node',
        'vps.unitmail.example.com',
        'WGPubKey2345678901bcdefghijklmnopqrstuvw==',
        'vps.example.com:51820',
        ARRAY['10.0.0.2/32'],
        NOW() - INTERVAL '1 hour',
        NOW() - INTERVAL '15 days'
    ),
    -- Admin's mesh peers (central node)
    (
        'mp001-0000-0000-0000-000000000003',
        'c3d4e5f6-a7b8-9012-cdef-345678901234',
        'Central Hub',
        'hub.unitmail.local',
        'WGPubKey3456789012cdefghijklmnopqrstuvwx==',
        'hub.unitmail.local:51820',
        ARRAY['10.0.0.0/24'],
        NOW(),
        NOW() - INTERVAL '60 days'
    );


-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Test data created:
-- - 3 users (alice, bob, admin)
-- - 15 folders (system + custom)
-- - 7 messages (various states)
-- - 6 contacts
-- - 4 queue items (various statuses)
-- - 5 config entries
-- - 3 mesh peers
--
-- Test credentials:
-- - Email: alice@test.unitmail.local, Password: testpass123
-- - Email: bob@test.unitmail.local, Password: testpass123
-- - Email: admin@test.unitmail.local, Password: testpass123
-- ============================================================================
