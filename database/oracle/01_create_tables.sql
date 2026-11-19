-- Oracle 19c+ SQL. Run once, with F5, while connected as REWRITE_APP.
-- No DROP, DELETE, user creation or sample production data is performed here.
-- Oracle DDL commits automatically. Do not rerun after a partial failure:
-- inspect the failing statement and ask the DBA to complete the installation.
SET DEFINE OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

DECLARE
    v_existing NUMBER;
    v_charset VARCHAR2(100);
BEGIN
    IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'REWRITE_APP'
       OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'REWRITE_APP' THEN
        RAISE_APPLICATION_ERROR(-20010, 'Connect as REWRITE_APP. Do not create application tables in SYSTEM.');
    END IF;
    IF DBMS_DB_VERSION.VERSION < 19 THEN
        RAISE_APPLICATION_ERROR(-20011, 'This installation targets Oracle 19c or newer.');
    END IF;
    SELECT value INTO v_charset FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET';
    IF v_charset <> 'AL32UTF8' THEN
        RAISE_APPLICATION_ERROR(-20012, 'Ask the DBA to confirm Unicode storage. This schema expects AL32UTF8 for Arabic and English.');
    END IF;
    SELECT COUNT(*) INTO v_existing FROM user_tables WHERE table_name LIKE 'RW\_%' ESCAPE '\' OR table_name LIKE 'HARF\_%' ESCAPE '\';
    IF v_existing > 0 THEN
        RAISE_APPLICATION_ERROR(-20013, 'Application tables already exist. Nothing was replaced. Run 02_verify_installation.sql.');
    END IF;
END;
/

CREATE TABLE genai_harf_schema_versions (
    version_id VARCHAR2(30 CHAR) PRIMARY KEY,
    description VARCHAR2(300 CHAR) NOT NULL,
    installed_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE TABLE genai_harf_channels (
    channel_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_name VARCHAR2(200 CHAR) NOT NULL,
    is_active NUMBER(1) DEFAULT 1 NOT NULL CHECK (is_active IN (0,1)),
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    deleted_at TIMESTAMP(6) WITH TIME ZONE,
    deleted_by VARCHAR2(320 CHAR),
    config_json CLOB NOT NULL CHECK (config_json IS JSON)
);

CREATE TABLE genai_harf_users (
    email VARCHAR2(320 CHAR) PRIMARY KEY,
    display_name VARCHAR2(240 CHAR) NOT NULL,
    role_name VARCHAR2(30 CHAR) NOT NULL CHECK (role_name IN ('super_admin','channel_admin','approval_admin','user')),
    channel_id VARCHAR2(80 CHAR) REFERENCES genai_harf_channels(channel_id),
    is_active NUMBER(1) DEFAULT 1 NOT NULL CHECK (is_active IN (0,1)),
    approval_layer NUMBER(1) CHECK (approval_layer BETWEEN 1 AND 3),
    directory_id VARCHAR2(400 CHAR) UNIQUE,
    auth_source VARCHAR2(20 CHAR) DEFAULT 'local' NOT NULL,
    password_hash VARCHAR2(500 CHAR),
    review_languages CLOB CHECK (review_languages IS JSON),
    profile_json CLOB NOT NULL CHECK (profile_json IS JSON),
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT rw_user_reviewer_ck CHECK (role_name <> 'approval_admin' OR approval_layer IS NOT NULL)
);
CREATE INDEX rw_users_channel_ix ON genai_harf_users(channel_id, role_name, is_active);

CREATE TABLE genai_harf_instructions (
    channel_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_channels(channel_id),
    module_id VARCHAR2(100 CHAR) NOT NULL,
    file_name VARCHAR2(300 CHAR) NOT NULL,
    display_name VARCHAR2(300 CHAR) NOT NULL,
    instruction_kind VARCHAR2(20 CHAR) NOT NULL CHECK (instruction_kind IN ('system','template','guide','reference')),
    is_active NUMBER(1) DEFAULT 1 NOT NULL CHECK (is_active IN (0,1)),
    current_version NUMBER(10) NOT NULL CHECK (current_version >= 1),
    checksum VARCHAR2(64 CHAR) NOT NULL,
    content_md CLOB NOT NULL,
    metadata_json CLOB NOT NULL CHECK (metadata_json IS JSON),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT rw_instructions_pk PRIMARY KEY (channel_id, module_id)
);

CREATE TABLE genai_harf_instruction_versions (
    channel_id VARCHAR2(80 CHAR) NOT NULL,
    module_id VARCHAR2(100 CHAR) NOT NULL,
    version_no NUMBER(10) NOT NULL CHECK (version_no >= 1),
    content_md CLOB NOT NULL,
    checksum VARCHAR2(64 CHAR) NOT NULL,
    actor_name VARCHAR2(240 CHAR) NOT NULL,
    actor_email VARCHAR2(320 CHAR),
    actor_role VARCHAR2(30 CHAR) NOT NULL,
    change_action VARCHAR2(40 CHAR) NOT NULL,
    change_note CLOB,
    restored_from NUMBER(10),
    character_count NUMBER(12) NOT NULL CHECK (character_count >= 0),
    word_count NUMBER(12) NOT NULL CHECK (word_count >= 0),
    line_count NUMBER(12) NOT NULL CHECK (line_count >= 0),
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    CONSTRAINT rw_instruction_versions_pk PRIMARY KEY (channel_id, module_id, version_no),
    CONSTRAINT rw_instr_versions_parent_fk FOREIGN KEY (channel_id, module_id) REFERENCES genai_harf_instructions(channel_id, module_id)
);

CREATE TABLE genai_harf_batches (
    batch_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_channels(channel_id),
    title VARCHAR2(500 CHAR) NOT NULL,
    archive_name VARCHAR2(200 CHAR),
    task_name VARCHAR2(100 CHAR),
    content_channel VARCHAR2(160 CHAR),
    audience VARCHAR2(240 CHAR),
    product_type VARCHAR2(240 CHAR),
    user_instructions CLOB,
    status VARCHAR2(30 CHAR) NOT NULL CHECK (status IN ('draft','pending_layer_1','pending_layer_2','pending_layer_3','returned_to_user','approved','rejected')),
    current_layer NUMBER(1) DEFAULT 0 NOT NULL CHECK (current_layer BETWEEN 0 AND 3),
    progress NUMBER(3) DEFAULT 0 NOT NULL CHECK (progress BETWEEN 0 AND 100),
    created_by_email VARCHAR2(320 CHAR) NOT NULL,
    created_by_name VARCHAR2(240 CHAR) NOT NULL,
    created_by_id VARCHAR2(400 CHAR),
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    submitted_at TIMESTAMP(6) WITH TIME ZONE,
    completed_at TIMESTAMP(6) WITH TIME ZONE,
    approval_method VARCHAR2(40 CHAR) DEFAULT 'normal_review' NOT NULL,
    payload_json CLOB NOT NULL CHECK (payload_json IS JSON)
);
CREATE INDEX rw_batches_queue_ix ON genai_harf_batches(channel_id, status, current_layer, updated_at);
CREATE INDEX rw_batches_author_ix ON genai_harf_batches(created_by_email, created_at);

CREATE TABLE genai_harf_copy_items (
    batch_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_batches(batch_id),
    item_id VARCHAR2(160 CHAR) NOT NULL,
    source_filename VARCHAR2(500 CHAR),
    archive_name VARCHAR2(200 CHAR),
    output_key VARCHAR2(160 CHAR),
    output_name VARCHAR2(500 CHAR),
    source_text CLOB,
    generation_instructions CLOB,
    format_instructions CLOB,
    source_bytes NUMBER(14) CHECK (source_bytes >= 0),
    source_characters NUMBER(12) CHECK (source_characters >= 0),
    source_words NUMBER(12) CHECK (source_words >= 0),
    metadata_json CLOB NOT NULL CHECK (metadata_json IS JSON),
    CONSTRAINT rw_copy_items_pk PRIMARY KEY (batch_id, item_id)
);

CREATE TABLE genai_harf_outputs (
    batch_id VARCHAR2(80 CHAR) NOT NULL,
    item_id VARCHAR2(160 CHAR) NOT NULL,
    language_code VARCHAR2(10 CHAR) NOT NULL CHECK (language_code IN ('en','ar')),
    version_no NUMBER(10) DEFAULT 1 NOT NULL CHECK (version_no >= 1),
    output_text CLOB NOT NULL,
    guideline_score NUMBER(5,2) CHECK (guideline_score BETWEEN 0 AND 100),
    character_count NUMBER(12) CHECK (character_count >= 0),
    word_count NUMBER(12) CHECK (word_count >= 0),
    quality_report CLOB CHECK (quality_report IS JSON),
    metadata_json CLOB NOT NULL CHECK (metadata_json IS JSON),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT rw_outputs_pk PRIMARY KEY (batch_id, item_id, language_code),
    CONSTRAINT rw_outputs_item_fk FOREIGN KEY (batch_id, item_id) REFERENCES genai_harf_copy_items(batch_id, item_id)
);

CREATE TABLE genai_harf_copy_versions (
    batch_id VARCHAR2(80 CHAR) NOT NULL,
    item_id VARCHAR2(160 CHAR) NOT NULL,
    language_code VARCHAR2(10 CHAR) NOT NULL,
    version_no NUMBER(10) NOT NULL CHECK (version_no >= 1),
    output_text CLOB NOT NULL,
    actor_email VARCHAR2(320 CHAR),
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    change_request CLOB,
    metadata_json CLOB NOT NULL CHECK (metadata_json IS JSON),
    CONSTRAINT rw_copy_versions_pk PRIMARY KEY (batch_id, item_id, language_code, version_no),
    CONSTRAINT rw_copy_versions_output_fk FOREIGN KEY (batch_id, item_id, language_code) REFERENCES genai_harf_outputs(batch_id, item_id, language_code)
);

CREATE TABLE genai_harf_approval_events (
    event_id VARCHAR2(80 CHAR) PRIMARY KEY,
    batch_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_batches(batch_id),
    event_action VARCHAR2(80 CHAR) NOT NULL,
    actor_email VARCHAR2(320 CHAR),
    actor_name VARCHAR2(240 CHAR) NOT NULL,
    actor_role VARCHAR2(30 CHAR),
    from_layer NUMBER(1) CHECK (from_layer BETWEEN 0 AND 3),
    to_layer NUMBER(1) CHECK (to_layer BETWEEN 0 AND 3),
    event_note CLOB,
    occurred_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    payload_json CLOB NOT NULL CHECK (payload_json IS JSON)
);
CREATE INDEX rw_approval_events_batch_ix ON genai_harf_approval_events(batch_id, occurred_at);

CREATE TABLE genai_harf_language_approvals (
    batch_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_batches(batch_id),
    layer_no NUMBER(1) NOT NULL CHECK (layer_no BETWEEN 1 AND 3),
    language_code VARCHAR2(10 CHAR) NOT NULL CHECK (language_code IN ('en','ar')),
    reviewer_email VARCHAR2(320 CHAR),
    reviewer_name VARCHAR2(240 CHAR) NOT NULL,
    approved_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    approval_note CLOB,
    payload_json CLOB NOT NULL CHECK (payload_json IS JSON),
    CONSTRAINT rw_language_approvals_pk PRIMARY KEY (batch_id, layer_no, language_code)
);

CREATE TABLE genai_harf_notifications (
    notification_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_id VARCHAR2(80 CHAR) REFERENCES genai_harf_channels(channel_id),
    batch_id VARCHAR2(80 CHAR) REFERENCES genai_harf_batches(batch_id),
    recipient_email VARCHAR2(320 CHAR) NOT NULL,
    title VARCHAR2(500 CHAR) NOT NULL,
    message_text CLOB NOT NULL,
    notification_kind VARCHAR2(80 CHAR) NOT NULL,
    is_read NUMBER(1) DEFAULT 0 NOT NULL CHECK (is_read IN (0,1)),
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    payload_json CLOB NOT NULL CHECK (payload_json IS JSON)
);
CREATE INDEX rw_notifications_inbox_ix ON genai_harf_notifications(recipient_email, is_read, created_at);

CREATE TABLE genai_harf_activity (
    activity_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_id VARCHAR2(80 CHAR) REFERENCES genai_harf_channels(channel_id),
    actor_email VARCHAR2(320 CHAR) NOT NULL,
    actor_name VARCHAR2(240 CHAR) NOT NULL,
    actor_id VARCHAR2(400 CHAR),
    event_action VARCHAR2(240 CHAR) NOT NULL,
    detail_text CLOB,
    occurred_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    metadata_json CLOB NOT NULL CHECK (metadata_json IS JSON)
);
CREATE INDEX rw_activity_channel_ix ON genai_harf_activity(channel_id, occurred_at);
CREATE INDEX rw_activity_actor_ix ON genai_harf_activity(actor_email, occurred_at);

CREATE TABLE genai_harf_feedback (
    feedback_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_channels(channel_id),
    workspace_name VARCHAR2(30 CHAR) DEFAULT 'rewrite' NOT NULL,
    user_email VARCHAR2(320 CHAR) NOT NULL,
    user_name VARCHAR2(240 CHAR) NOT NULL,
    fingerprint VARCHAR2(64 CHAR) NOT NULL,
    rating VARCHAR2(10 CHAR) NOT NULL CHECK (rating IN ('up','down')),
    reason_text CLOB,
    snapshot_json CLOB NOT NULL CHECK (snapshot_json IS JSON),
    instruction_manifest CLOB NOT NULL CHECK (instruction_manifest IS JSON),
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    review_status VARCHAR2(20 CHAR) DEFAULT 'new' NOT NULL CHECK (review_status IN ('new','reviewed')),
    admin_note CLOB,
    reviewed_by VARCHAR2(320 CHAR),
    reviewed_at TIMESTAMP(6) WITH TIME ZONE,
    CONSTRAINT rw_feedback_vote_uk UNIQUE (user_email, channel_id, fingerprint)
);
CREATE INDEX rw_feedback_channel_ix ON genai_harf_feedback(channel_id, updated_at);

CREATE TABLE genai_harf_channel_limits (
    channel_id VARCHAR2(80 CHAR) PRIMARY KEY REFERENCES genai_harf_channels(channel_id),
    monthly_limit NUMBER(12) NOT NULL CHECK (monthly_limit >= 0)
);

CREATE TABLE genai_harf_user_limits (
    channel_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_channels(channel_id),
    principal_id VARCHAR2(400 CHAR) NOT NULL,
    monthly_limit NUMBER(12) NOT NULL CHECK (monthly_limit >= 0),
    CONSTRAINT rw_user_limits_pk PRIMARY KEY (channel_id, principal_id)
);

CREATE TABLE genai_harf_request_usage (
    request_id VARCHAR2(80 CHAR) PRIMARY KEY,
    channel_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_channels(channel_id),
    principal_id VARCHAR2(400 CHAR) NOT NULL,
    month_key VARCHAR2(7 CHAR) NOT NULL CHECK (REGEXP_LIKE(month_key, '^[0-9]{4}-[0-9]{2}$')),
    request_state VARCHAR2(20 CHAR) NOT NULL CHECK (request_state IN ('pending','completed','released')),
    expires_at TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP(6) WITH TIME ZONE NOT NULL
);
CREATE INDEX rw_request_usage_lookup_ix ON genai_harf_request_usage(channel_id, month_key, principal_id, request_state);

CREATE VIEW rw_approval_queue AS
SELECT batch_id, channel_id, title, archive_name, status, current_layer, progress,
       created_by_email, created_by_name, created_at, submitted_at, updated_at
FROM genai_harf_batches
WHERE submitted_at IS NOT NULL AND status <> 'draft';

CREATE VIEW rw_channel_request_usage AS
SELECT channel_id, month_key, COUNT(*) AS used_requests
FROM genai_harf_request_usage
WHERE request_state = 'completed' OR (request_state = 'pending' AND expires_at > SYSTIMESTAMP)
GROUP BY channel_id, month_key;

INSERT INTO genai_harf_schema_versions(version_id, description)
VALUES ('001', 'Rewrite application tables, approval and request-usage views');
COMMIT;
PROMPT Rewrite tables created. Run 02_verify_installation.sql next.
