-- WhatsApp module tables (SQLite). Generated from app/whatsapp/models.py.
--
-- You normally do NOT need to run this by hand: app/whatsapp/__init__.py
-- (init_app) creates any missing whatsapp_* table and index on startup
-- with CREATE ... IF NOT EXISTS semantics. It never alters or drops anything.
-- Kept here for review, manual setup, or running with sqlite3:
--     sqlite3 instance/database.db < migrations/sqlite_whatsapp_module.sql
--
-- Only NEW tables are created. Existing tables (users, customers, sales,
-- tasks) are referenced by foreign key and are never modified.
--
-- Backup taken before the first run:
--     instance/database.db.bak-before-whatsapp-20261024
--
-- ROLLBACK (removes the module's data only; stop the app first):
--     PRAGMA foreign_keys=OFF;
--     DROP TABLE IF EXISTS whatsapp_message_status_events;
--     DROP TABLE IF EXISTS whatsapp_automation_logs;
--     DROP TABLE IF EXISTS whatsapp_internal_notes;
--     DROP TABLE IF EXISTS whatsapp_messages;
--     DROP TABLE IF EXISTS whatsapp_campaign_recipients;
--     DROP TABLE IF EXISTS whatsapp_campaigns;
--     DROP TABLE IF EXISTS whatsapp_automations;
--     DROP TABLE IF EXISTS whatsapp_conversations;
--     DROP TABLE IF EXISTS whatsapp_contacts;
--     DROP TABLE IF EXISTS whatsapp_templates;
--     DROP TABLE IF EXISTS whatsapp_webhook_events;
--     DROP TABLE IF EXISTS whatsapp_api_errors;
--     DROP TABLE IF EXISTS whatsapp_audit_logs;
--     DROP TABLE IF EXISTS whatsapp_user_permissions;
--     DROP TABLE IF EXISTS whatsapp_settings;
--     DROP TABLE IF EXISTS whatsapp_state;
--     PRAGMA foreign_keys=ON;
-- and remove the "whatsapp.init_app(app)" lines from app/__init__.py.
-- Full recovery instead: stop the app and copy the backup file over
-- instance/database.db (this also loses any CRM data entered since).

CREATE TABLE IF NOT EXISTS whatsapp_settings (
	id INTEGER NOT NULL, 
	app_id VARCHAR(64), 
	app_secret_enc TEXT, 
	access_token_enc TEXT, 
	verify_token_enc TEXT, 
	phone_number_id VARCHAR(64), 
	waba_id VARCHAR(64), 
	graph_version VARCHAR(10) NOT NULL, 
	default_country_code VARCHAR(4) NOT NULL, 
	display_phone_number VARCHAR(40), 
	verified_name VARCHAR(200), 
	quality_rating VARCHAR(20), 
	messaging_limit VARCHAR(40), 
	connection_status VARCHAR(20) NOT NULL, 
	connection_message VARCHAR(500), 
	last_test_at DATETIME, 
	connection_verified_at DATETIME, 
	webhook_subscribed BOOLEAN, 
	last_webhook_at DATETIME, 
	last_webhook_ok_at DATETIME, 
	templates_synced_at DATETIME, 
	auto_mark_read BOOLEAN NOT NULL, 
	optout_keywords VARCHAR(255) NOT NULL, 
	max_upload_mb INTEGER NOT NULL, 
	media_retention_days INTEGER NOT NULL, 
	log_retention_days INTEGER NOT NULL, 
	campaigns_enabled BOOLEAN NOT NULL, 
	campaign_rate_per_minute INTEGER NOT NULL, 
	notify_assigned_by_email BOOLEAN NOT NULL, 
	updated_by INTEGER, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_whatsapp_settings_conn CHECK (connection_status IN ('unknown', 'connected', 'error')), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_user_permissions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	can_view BOOLEAN NOT NULL, 
	can_view_all BOOLEAN NOT NULL, 
	can_reply BOOLEAN NOT NULL, 
	can_assign BOOLEAN NOT NULL, 
	can_manage_contacts BOOLEAN NOT NULL, 
	can_export BOOLEAN NOT NULL, 
	can_manage_templates BOOLEAN NOT NULL, 
	can_manage_campaigns BOOLEAN NOT NULL, 
	can_manage_automations BOOLEAN NOT NULL, 
	can_view_reports BOOLEAN NOT NULL, 
	can_manage_settings BOOLEAN NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS whatsapp_contacts (
	id INTEGER NOT NULL, 
	wa_id VARCHAR(20) NOT NULL, 
	name VARCHAR(150), 
	profile_name VARCHAR(150), 
	email VARCHAR(120), 
	customer_id INTEGER, 
	assigned_to_id INTEGER, 
	tags VARCHAR(500) NOT NULL, 
	consent_status VARCHAR(12) NOT NULL, 
	consent_source VARCHAR(120), 
	consent_at DATETIME, 
	opted_out_at DATETIME, 
	last_message_at DATETIME, 
	notes TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_whatsapp_contacts_consent CHECK (consent_status IN ('unknown', 'opted_in', 'opted_out')), 
	UNIQUE (wa_id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_assigned ON whatsapp_contacts (assigned_to_id);
CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_consent ON whatsapp_contacts (consent_status);
CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_created ON whatsapp_contacts (created_at);
CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_customer ON whatsapp_contacts (customer_id);

CREATE TABLE IF NOT EXISTS whatsapp_conversations (
	id INTEGER NOT NULL, 
	contact_id INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	assigned_to_id INTEGER, 
	is_starred BOOLEAN NOT NULL, 
	unread_count INTEGER NOT NULL, 
	last_message_at DATETIME, 
	last_message_preview VARCHAR(200), 
	last_message_direction VARCHAR(3), 
	last_inbound_at DATETIME, 
	first_response_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_whatsapp_conv_status CHECK (status IN ('open', 'pending', 'resolved')), 
	UNIQUE (contact_id), 
	FOREIGN KEY(contact_id) REFERENCES whatsapp_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_conv_activity ON whatsapp_conversations (last_message_at);
CREATE INDEX IF NOT EXISTS ix_whatsapp_conv_assigned ON whatsapp_conversations (assigned_to_id, status);
CREATE INDEX IF NOT EXISTS ix_whatsapp_conv_updated ON whatsapp_conversations (updated_at);

CREATE TABLE IF NOT EXISTS whatsapp_templates (
	id INTEGER NOT NULL, 
	meta_id VARCHAR(64), 
	name VARCHAR(512) NOT NULL, 
	language VARCHAR(15) NOT NULL, 
	category VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	parameter_format VARCHAR(12) NOT NULL, 
	components_json TEXT NOT NULL, 
	rejected_reason VARCHAR(255), 
	synced_at DATETIME, 
	removed_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_whatsapp_template_name_lang UNIQUE (name, language)
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_templates_status ON whatsapp_templates (status);

CREATE TABLE IF NOT EXISTS whatsapp_campaigns (
	id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	template_id INTEGER, 
	params_json TEXT NOT NULL, 
	tag_filter VARCHAR(255) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	scheduled_at DATETIME, 
	started_at DATETIME, 
	completed_at DATETIME, 
	status_message VARCHAR(500), 
	created_by INTEGER, 
	confirmed_by INTEGER, 
	confirmed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_whatsapp_campaign_status CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled', 'failed')), 
	FOREIGN KEY(template_id) REFERENCES whatsapp_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(confirmed_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_status ON whatsapp_campaigns (status, scheduled_at);

CREATE TABLE IF NOT EXISTS whatsapp_automations (
	id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	"trigger" VARCHAR(30) NOT NULL, 
	conditions_json TEXT NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	action_config_json TEXT NOT NULL, 
	is_enabled BOOLEAN NOT NULL, 
	dry_run BOOLEAN NOT NULL, 
	created_by INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	last_run_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_automation_trigger ON whatsapp_automations ("trigger", is_enabled);

CREATE TABLE IF NOT EXISTS whatsapp_campaign_recipients (
	id INTEGER NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	contact_id INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	message_id INTEGER, 
	attempts INTEGER NOT NULL, 
	error VARCHAR(300), 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_whatsapp_campaign_recipient UNIQUE (campaign_id, contact_id), 
	FOREIGN KEY(campaign_id) REFERENCES whatsapp_campaigns (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES whatsapp_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(message_id) REFERENCES whatsapp_messages (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_cr_status ON whatsapp_campaign_recipients (campaign_id, status);

CREATE TABLE IF NOT EXISTS whatsapp_messages (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	direction VARCHAR(3) NOT NULL, 
	wamid VARCHAR(128), 
	client_ref VARCHAR(36), 
	msg_type VARCHAR(20) NOT NULL, 
	body TEXT, 
	media_id VARCHAR(64), 
	media_mime VARCHAR(100), 
	media_filename VARCHAR(255), 
	media_size INTEGER, 
	media_local_path VARCHAR(255), 
	template_name VARCHAR(512), 
	template_language VARCHAR(15), 
	template_params TEXT, 
	context_wamid VARCHAR(128), 
	extra_json TEXT, 
	status VARCHAR(10) NOT NULL, 
	error_code VARCHAR(20), 
	error_title VARCHAR(200), 
	error_detail VARCHAR(500), 
	sent_by_id INTEGER, 
	automation_id INTEGER, 
	campaign_recipient_id INTEGER, 
	retry_of_id INTEGER, 
	timestamp DATETIME NOT NULL, 
	status_updated_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_whatsapp_msg_direction CHECK (direction IN ('in', 'out')), 
	FOREIGN KEY(conversation_id) REFERENCES whatsapp_conversations (id) ON DELETE CASCADE, 
	UNIQUE (wamid), 
	UNIQUE (client_ref), 
	FOREIGN KEY(sent_by_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(automation_id) REFERENCES whatsapp_automations (id) ON DELETE SET NULL, 
	FOREIGN KEY(campaign_recipient_id) REFERENCES whatsapp_campaign_recipients (id) ON DELETE SET NULL, 
	FOREIGN KEY(retry_of_id) REFERENCES whatsapp_messages (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_msg_conv ON whatsapp_messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS ix_whatsapp_msg_status ON whatsapp_messages (direction, status);
CREATE INDEX IF NOT EXISTS ix_whatsapp_msg_status_upd ON whatsapp_messages (status_updated_at);
CREATE INDEX IF NOT EXISTS ix_whatsapp_msg_ts ON whatsapp_messages (timestamp);

CREATE TABLE IF NOT EXISTS whatsapp_message_status_events (
	id INTEGER NOT NULL, 
	message_id INTEGER, 
	wamid VARCHAR(128) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	status_at DATETIME NOT NULL, 
	error_code VARCHAR(20), 
	error_title VARCHAR(200), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_whatsapp_status_event UNIQUE (wamid, status, status_at), 
	FOREIGN KEY(message_id) REFERENCES whatsapp_messages (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_status_msg ON whatsapp_message_status_events (message_id);

CREATE TABLE IF NOT EXISTS whatsapp_automation_logs (
	id INTEGER NOT NULL, 
	automation_id INTEGER NOT NULL, 
	event_key VARCHAR(120) NOT NULL, 
	result VARCHAR(10) NOT NULL, 
	detail VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_whatsapp_automation_event UNIQUE (automation_id, event_key), 
	FOREIGN KEY(automation_id) REFERENCES whatsapp_automations (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_automation_logs_created ON whatsapp_automation_logs (created_at);

CREATE TABLE IF NOT EXISTS whatsapp_webhook_events (
	id INTEGER NOT NULL, 
	dedupe_key VARCHAR(64) NOT NULL, 
	received_at DATETIME NOT NULL, 
	signature_ok BOOLEAN NOT NULL, 
	processed_ok BOOLEAN NOT NULL, 
	summary VARCHAR(300), 
	error VARCHAR(300), 
	PRIMARY KEY (id), 
	UNIQUE (dedupe_key)
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_webhook_received ON whatsapp_webhook_events (received_at);

CREATE TABLE IF NOT EXISTS whatsapp_api_errors (
	id INTEGER NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	code VARCHAR(20), 
	kind VARCHAR(30), 
	message VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_api_errors_created ON whatsapp_api_errors (created_at);

CREATE TABLE IF NOT EXISTS whatsapp_internal_notes (
	id INTEGER NOT NULL, 
	contact_id INTEGER NOT NULL, 
	user_id INTEGER, 
	body TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(contact_id) REFERENCES whatsapp_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_notes_contact ON whatsapp_internal_notes (contact_id);

CREATE TABLE IF NOT EXISTS whatsapp_audit_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	target VARCHAR(120), 
	detail VARCHAR(500), 
	ip VARCHAR(45), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_whatsapp_audit_created ON whatsapp_audit_logs (created_at);

CREATE TABLE IF NOT EXISTS whatsapp_state (
	"key" VARCHAR(60) NOT NULL, 
	value VARCHAR(255), 
	updated_at DATETIME, 
	PRIMARY KEY ("key")
);

