# Social Media module: setup, deployment and rollback

Sidebar → **Social Media**. The module publishes and schedules posts to Facebook Pages, Instagram
professional accounts and LinkedIn, syncs metrics, and manages Meta ad campaigns. All code is in
`app/social_media/`. It uses its own `social_*` tables, and its templates and static files live in
`templates/social_media/` and `static/social_media/`.

## 1. Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SOCIAL_MEDIA_ENCRYPTION_KEY` | **Yes** | Fernet key used to encrypt app secrets and OAuth tokens. Without it, credentials can't be saved and accounts can't be connected; the module refuses rather than storing plaintext. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. **Back it up.** If you lose it, every account has to be reconnected. |
| `SOCIAL_MEDIA_PUBLIC_BASE_URL` | Recommended | Public HTTPS address of the CRM, for example `https://crm.example.com`. You can set this instead in *API Settings › Media Storage*, which takes precedence. It's used for the OAuth redirect URIs and for Instagram media links. |
| `SOCIAL_MEDIA_SCHEDULER_DISABLED` | Optional | Set to `1` to stop the in-process publisher. If you do, run `flask --app run social-media-tick` from cron every minute. |

Never put real values in the repository. App IDs and secrets are entered in *API Settings*, where they're stored encrypted.

## 2. OAuth callback URLs

These are built from the public base URL. The exact values for your install are shown, with copy buttons, in
*API Settings › Meta / Facebook* and *› LinkedIn*:

- Meta: `<PUBLIC_BASE_URL>/social-media/oauth/meta/callback`
- LinkedIn: `<PUBLIC_BASE_URL>/social-media/oauth/linkedin/callback`

Both providers require HTTPS outside localhost.

## 3. Meta (Facebook, Instagram, Ads)

1. https://developers.facebook.com/apps → create a **Business** app.
2. *App settings › Basic*: copy the App ID and App Secret into *API Settings › Meta / Facebook*. Also add a privacy policy URL and the app domain.
3. Add **Facebook Login for Business**. Optionally create a Configuration and paste its ID.
4. Add the Meta callback URL above as a *Valid OAuth Redirect URI* (keep Strict Mode on).
5. Add the **Instagram** product (Instagram API with Facebook Login). The Instagram account must be a Business or Creator account, linked to the Facebook Page.
6. Request only the permissions you use:
   - Facebook publishing: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
   - Insights: `read_insights`, `instagram_manage_insights`
   - Instagram: `instagram_basic`, `instagram_content_publish`
   - Business-owned Pages: `business_management`
   - Ads (enable in *API Settings › Facebook Ads*): `ads_read`, `ads_management`

   In Development mode these work only for people who have a role on the app.
7. *Connected Accounts › Connect Facebook & Instagram* → approve on Facebook → select your Pages and Instagram accounts → click **Test** on each one.
8. For production use by people without an app role: complete **Business Verification** and **App Review** for each advanced permission (and Marketing API access for ads), then switch the app to **Live**.

Docs: https://developers.facebook.com/docs/pages-api/ · https://developers.facebook.com/docs/instagram-platform/ · https://developers.facebook.com/docs/marketing-apis/

## 4. LinkedIn

1. https://www.linkedin.com/developers/apps → create an app linked to your company Page. A Page admin must verify it.
2. *Auth* tab: copy the Client ID and Client Secret into *API Settings › LinkedIn*, and add the LinkedIn callback URL above.
3. *Products* tab: add **Sign In with LinkedIn using OpenID Connect** (`openid profile email`) and **Share on LinkedIn** (`w_member_social`). Both are self-serve.
4. Company pages: request the **Community Management API** (`w_organization_social`, `r_organization_social`, `rw_organization_admin`). LinkedIn reviews this request and may decline it. Until it's approved, only personal-profile posting works.
5. *Connected Accounts › Connect LinkedIn* → choose your profile and/or the pages you administer.

Docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api

## 5. Scheduler

- By default it runs every minute inside the web process (APScheduler, already a CRM dependency), the same way as the CRM's other jobs.
- Jobs are rows in `social_post_destinations`, so they survive restarts. Each one is claimed with an atomic UPDATE, so several gunicorn workers or a cron tick running alongside cannot publish the same post twice.
- Temporary errors retry with exponential backoff. If the outcome is unknown (for example, a timeout after the request was sent), the destination is marked **needs review** instead of being retried blindly.
- Health, the last run and the next scheduled post are shown in *API Settings › Scheduler*.

## 6. Database

Tables are created automatically at startup (`checkfirst`, additive only). The equivalent SQL is in
`migrations/sqlite_social_media_module.sql`. No existing table is altered.

## 7. Rollback

1. Remove the 3-line `social_media.init_app(app)` block from `app/__init__.py`, and the `Social Media` group from
   `app/templates/components/sidebar_nav.html`. The CRM then runs exactly as before.
2. Optional: delete `app/social_media/`, `app/templates/social_media/`, `app/static/social_media/` and
   `tests/test_social_media.py`.
3. Optional (destroys module data; back up the database first): drop the tables. Nothing else references them.
   ```sql
   DROP TABLE IF EXISTS social_ad_insights; DROP TABLE IF EXISTS social_ads; DROP TABLE IF EXISTS social_ad_sets;
   DROP TABLE IF EXISTS social_ad_campaigns; DROP TABLE IF EXISTS social_ad_accounts;
   DROP TABLE IF EXISTS social_post_insights; DROP TABLE IF EXISTS social_publish_attempts;
   DROP TABLE IF EXISTS social_post_destinations; DROP TABLE IF EXISTS social_post_media;
   DROP TABLE IF EXISTS social_posts; DROP TABLE IF EXISTS social_account_syncs;
   DROP TABLE IF EXISTS social_account_access; DROP TABLE IF EXISTS social_accounts;
   DROP TABLE IF EXISTS social_oauth_credentials; DROP TABLE IF EXISTS social_user_permissions;
   DROP TABLE IF EXISTS social_role_permissions; DROP TABLE IF EXISTS social_settings;
   DROP TABLE IF EXISTS social_audit_logs; DROP TABLE IF EXISTS social_notifications;
   ```
   Uploaded media is stored in `instance/social_media_media/`.

Nothing on Facebook, Instagram or LinkedIn is deleted by any of these steps. A git tag, `pre-social-media-module`, marks the state before this module was added.

## 8. Tests

`venv\Scripts\python.exe -m unittest tests.test_social_media -v` runs 34 tests against mocked APIs. Nothing is posted and no ad money is spent.
