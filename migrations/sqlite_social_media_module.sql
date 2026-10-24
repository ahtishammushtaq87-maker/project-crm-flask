-- Social Media module: new social_* tables only. No existing table is altered.
-- The app creates these automatically at startup (checkfirst), so running this file is optional.
-- Manual apply:  sqlite3 instance/database.db < migrations/sqlite_social_media_module.sql
-- Rollback: see SOCIAL_MEDIA_SETUP.md (DROP the social_* tables; nothing else references them).

CREATE TABLE IF NOT EXISTS social_settings (
	"key" VARCHAR(80) NOT NULL, 
	value TEXT, 
	is_secret BOOLEAN NOT NULL, 
	updated_by INTEGER, 
	updated_at DATETIME, 
	PRIMARY KEY ("key"), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS social_role_permissions (
	role VARCHAR(20) NOT NULL, 
	updated_at DATETIME, 
	can_view BOOLEAN NOT NULL, 
	can_view_accounts BOOLEAN NOT NULL, 
	can_manage_accounts BOOLEAN NOT NULL, 
	can_create_posts BOOLEAN NOT NULL, 
	can_edit_posts BOOLEAN NOT NULL, 
	can_publish BOOLEAN NOT NULL, 
	can_schedule BOOLEAN NOT NULL, 
	can_delete_posts BOOLEAN NOT NULL, 
	can_view_analytics BOOLEAN NOT NULL, 
	can_view_ads BOOLEAN NOT NULL, 
	can_manage_ads BOOLEAN NOT NULL, 
	can_approve_ad_spend BOOLEAN NOT NULL, 
	can_manage_settings BOOLEAN NOT NULL, 
	can_view_logs BOOLEAN NOT NULL, 
	PRIMARY KEY (role)
);


CREATE TABLE IF NOT EXISTS social_user_permissions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	updated_at DATETIME, 
	can_view BOOLEAN NOT NULL, 
	can_view_accounts BOOLEAN NOT NULL, 
	can_manage_accounts BOOLEAN NOT NULL, 
	can_create_posts BOOLEAN NOT NULL, 
	can_edit_posts BOOLEAN NOT NULL, 
	can_publish BOOLEAN NOT NULL, 
	can_schedule BOOLEAN NOT NULL, 
	can_delete_posts BOOLEAN NOT NULL, 
	can_view_analytics BOOLEAN NOT NULL, 
	can_view_ads BOOLEAN NOT NULL, 
	can_manage_ads BOOLEAN NOT NULL, 
	can_approve_ad_spend BOOLEAN NOT NULL, 
	can_manage_settings BOOLEAN NOT NULL, 
	can_view_logs BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS social_oauth_credentials (
	id INTEGER NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	token_type VARCHAR(20) NOT NULL, 
	external_user_id VARCHAR(120), 
	external_user_name VARCHAR(200), 
	access_token_enc TEXT NOT NULL, 
	refresh_token_enc TEXT, 
	scopes TEXT, 
	expires_at DATETIME, 
	refresh_expires_at DATETIME, 
	data_access_expires_at DATETIME, 
	expiry_known BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	last_error VARCHAR(500), 
	parent_id INTEGER, 
	owner_user_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES social_oauth_credentials (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_social_cred_provider_ext ON social_oauth_credentials (provider, token_type, external_user_id);

CREATE TABLE IF NOT EXISTS social_accounts (
	id INTEGER NOT NULL, 
	platform VARCHAR(20) NOT NULL, 
	account_type VARCHAR(20) NOT NULL, 
	remote_id VARCHAR(120) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	username VARCHAR(200), 
	picture_url VARCHAR(1000), 
	credential_id INTEGER, 
	parent_account_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	granted_permissions TEXT, 
	last_sync_at DATETIME, 
	last_test_at DATETIME, 
	last_error VARCHAR(500), 
	connected_by INTEGER, 
	connected_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_social_accounts_platform_remote UNIQUE (platform, remote_id), 
	CONSTRAINT ck_social_accounts_platform CHECK (platform IN ('facebook', 'instagram', 'linkedin')), 
	FOREIGN KEY(credential_id) REFERENCES social_oauth_credentials (id) ON DELETE SET NULL, 
	FOREIGN KEY(parent_account_id) REFERENCES social_accounts (id) ON DELETE SET NULL, 
	FOREIGN KEY(connected_by) REFERENCES users (id) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS social_account_access (
	account_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (account_id, user_id), 
	FOREIGN KEY(account_id) REFERENCES social_accounts (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS social_posts (
	id INTEGER NOT NULL, 
	title VARCHAR(200), 
	body TEXT NOT NULL, 
	hashtags VARCHAR(1000), 
	link_url VARCHAR(1000), 
	status VARCHAR(30) NOT NULL, 
	origin VARCHAR(10) NOT NULL, 
	scheduled_at DATETIME, 
	published_at DATETIME, 
	duplicated_from_id INTEGER, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(duplicated_from_id) REFERENCES social_posts (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_social_posts_scheduled ON social_posts (scheduled_at);
CREATE INDEX IF NOT EXISTS ix_social_posts_origin ON social_posts (origin);
CREATE INDEX IF NOT EXISTS ix_social_posts_status ON social_posts (status);

CREATE TABLE IF NOT EXISTS social_post_media (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	stored_name VARCHAR(200) NOT NULL, 
	original_name VARCHAR(255), 
	mime_type VARCHAR(80) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	width INTEGER, 
	height INTEGER, 
	position INTEGER NOT NULL, 
	public_enabled BOOLEAN NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(post_id) REFERENCES social_posts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_social_media_post ON social_post_media (post_id);

CREATE TABLE IF NOT EXISTS social_post_destinations (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	account_id INTEGER, 
	platform VARCHAR(20) NOT NULL, 
	custom_text TEXT, 
	ig_media_type VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	scheduled_at DATETIME, 
	next_attempt_at DATETIME, 
	failure_count INTEGER NOT NULL, 
	lock_token VARCHAR(40), 
	locked_at DATETIME, 
	remote_id VARCHAR(200), 
	remote_container_id VARCHAR(200), 
	remote_url VARCHAR(1000), 
	published_at DATETIME, 
	error_code VARCHAR(40), 
	error_kind VARCHAR(40), 
	error_message VARCHAR(500), 
	impressions INTEGER, 
	reach INTEGER, 
	engagements INTEGER, 
	insights_synced_at DATETIME, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_social_dest_post_account UNIQUE (post_id, account_id), 
	CONSTRAINT uq_social_dest_account_remote UNIQUE (account_id, remote_id), 
	FOREIGN KEY(post_id) REFERENCES social_posts (id) ON DELETE CASCADE, 
	FOREIGN KEY(account_id) REFERENCES social_accounts (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_social_dest_due ON social_post_destinations (status, scheduled_at);
CREATE INDEX IF NOT EXISTS ix_social_dest_retry ON social_post_destinations (status, next_attempt_at);

CREATE TABLE IF NOT EXISTS social_publish_attempts (
	id INTEGER NOT NULL, 
	destination_id INTEGER NOT NULL, 
	triggered_by VARCHAR(20) NOT NULL, 
	user_id INTEGER, 
	outcome VARCHAR(20) NOT NULL, 
	remote_id VARCHAR(200), 
	http_status INTEGER, 
	error_code VARCHAR(40), 
	error_message VARCHAR(500), 
	started_at DATETIME, 
	finished_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES social_post_destinations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_social_attempt_dest ON social_publish_attempts (destination_id);

CREATE TABLE IF NOT EXISTS social_post_insights (
	id INTEGER NOT NULL, 
	destination_id INTEGER NOT NULL, 
	captured_at DATETIME NOT NULL, 
	impressions INTEGER, 
	reach INTEGER, 
	engagements INTEGER, 
	likes INTEGER, 
	comments INTEGER, 
	shares INTEGER, 
	saves INTEGER, 
	clicks INTEGER, 
	video_views INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(destination_id) REFERENCES social_post_destinations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_social_insight_dest ON social_post_insights (destination_id, captured_at);

CREATE TABLE IF NOT EXISTS social_account_syncs (
	id INTEGER NOT NULL, 
	account_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	items INTEGER NOT NULL, 
	message VARCHAR(500), 
	started_at DATETIME, 
	finished_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES social_accounts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_social_sync_account ON social_account_syncs (account_id, started_at);

CREATE TABLE IF NOT EXISTS social_ad_accounts (
	id INTEGER NOT NULL, 
	credential_id INTEGER, 
	remote_id VARCHAR(60) NOT NULL, 
	name VARCHAR(200), 
	currency VARCHAR(10), 
	timezone_name VARCHAR(80), 
	account_status INTEGER, 
	is_selected BOOLEAN NOT NULL, 
	synced_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(credential_id) REFERENCES social_oauth_credentials (id) ON DELETE SET NULL, 
	UNIQUE (remote_id)
);


CREATE TABLE IF NOT EXISTS social_ad_campaigns (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	remote_id VARCHAR(60) NOT NULL, 
	name VARCHAR(400), 
	objective VARCHAR(60), 
	status VARCHAR(30), 
	effective_status VARCHAR(40), 
	daily_budget BIGINT, 
	lifetime_budget BIGINT, 
	start_time VARCHAR(40), 
	stop_time VARCHAR(40), 
	created_via_crm BOOLEAN NOT NULL, 
	created_by INTEGER, 
	synced_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES social_ad_accounts (id) ON DELETE CASCADE, 
	UNIQUE (remote_id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS social_ad_sets (
	id INTEGER NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	remote_id VARCHAR(60) NOT NULL, 
	name VARCHAR(400), 
	status VARCHAR(30), 
	effective_status VARCHAR(40), 
	daily_budget BIGINT, 
	lifetime_budget BIGINT, 
	optimization_goal VARCHAR(60), 
	billing_event VARCHAR(40), 
	targeting TEXT, 
	synced_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(campaign_id) REFERENCES social_ad_campaigns (id) ON DELETE CASCADE, 
	UNIQUE (remote_id)
);


CREATE TABLE IF NOT EXISTS social_ads (
	id INTEGER NOT NULL, 
	adset_id INTEGER NOT NULL, 
	remote_id VARCHAR(60) NOT NULL, 
	name VARCHAR(400), 
	status VARCHAR(30), 
	effective_status VARCHAR(40), 
	creative_id VARCHAR(60), 
	synced_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(adset_id) REFERENCES social_ad_sets (id) ON DELETE CASCADE, 
	UNIQUE (remote_id)
);


CREATE TABLE IF NOT EXISTS social_ad_insights (
	id INTEGER NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	date_start DATE NOT NULL, 
	date_stop DATE NOT NULL, 
	spend VARCHAR(30), 
	impressions BIGINT, 
	reach BIGINT, 
	clicks BIGINT, 
	link_clicks BIGINT, 
	ctr VARCHAR(30), 
	cpc VARCHAR(30), 
	cpm VARCHAR(30), 
	results TEXT, 
	captured_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_social_ad_insight_range UNIQUE (campaign_id, date_start, date_stop), 
	FOREIGN KEY(campaign_id) REFERENCES social_ad_campaigns (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS social_audit_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	target VARCHAR(200), 
	detail VARCHAR(1000), 
	success BOOLEAN NOT NULL, 
	ip VARCHAR(64), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_social_audit_created ON social_audit_logs (created_at);

CREATE TABLE IF NOT EXISTS social_notifications (
	id INTEGER NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	level VARCHAR(10) NOT NULL, 
	message VARCHAR(500) NOT NULL, 
	link VARCHAR(300), 
	created_at DATETIME, 
	read_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_social_notif_created ON social_notifications (created_at);

