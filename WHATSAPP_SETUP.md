# WhatsApp Module — Setup & Operations

The WhatsApp module connects the CRM to the official **Meta WhatsApp Business Platform (Cloud API)**.
It lives in `app/whatsapp/` and has its own `whatsapp_*` tables, templates and static files.

## 1. Server configuration

| Environment variable | Required | Purpose |
|---|---|---|
| `WHATSAPP_ENCRYPTION_KEY` | Strongly recommended | Fernet key that encrypts the access token, app secret and verify token in the database. Keep it out of the database and out of git. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. If you lose or change it, re-enter the three credentials in Settings. |
| `WHATSAPP_PUBLIC_BASE_URL` | Recommended | Public HTTPS address of the CRM, e.g. `https://crm.example.com`. Used for the webhook callback URL shown in Settings and for links built by background jobs (task links, invoice links). |
| `WHATSAPP_SCHEDULER_DISABLED=1` | Optional | Turns off the once-a-minute background job in this process. With several gunicorn workers, leave the job on in only one process, or turn it off everywhere and run `flask --app run whatsapp-tick` from cron every minute. |
| `SECRET_KEY` | Already used by the CRM | Must be a real secret in production: it signs sessions and CSRF tokens. |

Install the new dependency: `pip install -r requirements.txt` (adds `cryptography`, used only for credential encryption).

**HTTPS is required.** Meta only calls webhook URLs that use HTTPS with a valid certificate.

### Background job
APScheduler (already used by the CRM) runs every minute in the web process. It:
- sends campaign messages (at the configured rate),
- turns invoice events into automations,
- deletes cached media and old logs according to the retention settings.

The inbox, webhooks and manual sending work without it.

## 2. Database

- The tables are created automatically on startup by `whatsapp.init_app()` (create-if-missing only; nothing is altered or dropped).
- The raw SQL and rollback steps are in `migrations/sqlite_whatsapp_module.sql`.
- A backup was taken before the first migration: `instance/database.db.bak-before-whatsapp-20261024`.
- Received and sent media is stored privately in `instance/whatsapp_media/` (not under `static/`) and served only to signed-in staff who may see that conversation.

## 3. Meta setup (one time)

1. **Meta Business account.** Open [business.facebook.com](https://business.facebook.com) and verify the business if Meta asks you to.
2. **App.** At [developers.facebook.com/apps](https://developers.facebook.com/apps), create an app of type **Business** and add the **WhatsApp** product. Meta creates a test WhatsApp Business Account (WABA) and a test number.
3. **System User and token.** In Business Settings › Users › **System Users**:
   - create an Admin system user;
   - assign it the app and the WhatsApp Business Account, with full control;
   - click **Generate token**, choose the app, and tick `whatsapp_business_messaging` and `whatsapp_business_management`;
   - set the expiry to **Never**.
4. **IDs.** In the App Dashboard › WhatsApp › **API Setup**, copy the **Phone Number ID** and the **WhatsApp Business Account ID**.
5. **App secret.** In the App Dashboard › Settings › Basic, copy the **App Secret**.
6. **Enter the credentials.** In the CRM, open WhatsApp › Settings › **Connection**. Enter the Phone Number ID, WABA ID, access token and App Secret, set the Graph API version (default `v23.0`), then click **Save**. Next, click **Test connection**. The test calls `GET /{phone-number-id}`, `GET /{waba-id}` and `GET /{waba-id}/subscribed_apps`.

## 4. Webhook (callback URL and verify token)

1. In the CRM, open WhatsApp › Settings › **Webhook**. Click **Generate verify token** and copy the token, which is shown once. Then copy the **Callback URL**, which is `https://<your-domain>/webhooks/whatsapp`.
2. In the App Dashboard, open WhatsApp › **Configuration** › Webhook › **Edit**. Paste the Callback URL and the verify token, then click **Verify and save**.
3. Under **Webhook fields**, subscribe to:
   - `messages`: incoming messages and sent/delivered/read/failed statuses (required);
   - `message_template_status_update`: template approvals and rejections (recommended).
4. In the CRM, click **Subscribe app to WABA** (this calls `POST /{waba-id}/subscribed_apps`). Then run **Test connection** again; it should show "App subscribed to webhooks".

Security: every POST is verified with `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with the App Secret, compared in constant time). If no App Secret is saved, events are rejected.

## 5. Test number → first message

1. In API Setup, add your own phone to the test number's **recipient list**. Meta only lets test numbers message listed recipients; other numbers fail with error 131030.
2. From that phone, send "hi" to the test number. It should appear in WhatsApp › **Inbox** within about 5 seconds.
3. Reply from the inbox. You can send free-form messages for 24 hours after the customer's last message.
4. To start a conversation yourself, click **Sync from Meta** in Message Templates, then use the template button in the composer. Every WABA includes the approved `hello_world` template.

## 6. Production number

1. In WhatsApp Manager, add the real business phone number, verify it by SMS or voice, and set the display name. Meta reviews the display name.
2. Add a payment method to the WABA. Meta charges for template messages under its current pricing.
3. Put the production Phone Number ID (and WABA ID, if different) in Settings. Click **Save**, then **Test connection**.
4. Subscribe the production WABA to the app (step 4.4).
5. Expect a starting messaging limit tier. It rises with good quality ratings. Set Settings › Messaging › **Campaign rate** well below that limit.

## 7. Permissions in the CRM

- CRM admins have every WhatsApp permission.
- Admins grant other users access in WhatsApp › Settings › **Staff Permissions**. The permissions are: view, view all conversations, reply, assign, manage contacts, export, templates, campaigns, automations, reports and settings.
- Staff without "View all conversations" only see conversations assigned to them.
- The server checks every route and API call.
- Sensitive actions are recorded in Settings › Diagnostics › Audit log.

## 8. Routes

| Area | Routes |
|---|---|
| Pages | `/whatsapp/` (overview), `/whatsapp/inbox`, `/whatsapp/contacts` (+ `/new`, `/<id>/edit`, `/import`, `/export`, `/duplicates`, `/merge`), `/whatsapp/templates` (+ `/sync`, `/new`), `/whatsapp/campaigns` (+ `/new`, `/<id>`, `/<id>/confirm`, `/<id>/pause\|resume\|cancel\|retry\|delete`, `/<id>/export`), `/whatsapp/automations` (+ `/new`, `/<id>/edit`, `/<id>/enable\|disable\|live\|test_mode\|delete`), `/whatsapp/reports`, `/whatsapp/settings` (+ `/connection`, `/test`, `/subscribe`, `/options`, `/profile`, `/permissions`, `/clear`, `/generate-verify-token`), `/whatsapp/customer/<customer_id>`, `/whatsapp/invoice/<sale_id>/notify`, `/whatsapp/media/<message_id>` |
| Inbox API (JSON) | `/whatsapp/api/conversations`, `/api/conversations/<id>`, `/messages`, `/send`, `/send-media`, `/send-template`, `/update`, `/notes`, `/api/messages/<id>/retry`, `/api/poll`, `/api/templates/approved`, `/api/templates/<id>/preview`, `/api/contacts/search`, `/api/contacts/<id>/open`, `/api/customers/search`, `/whatsapp/campaigns/estimate` |
| Meta | `GET/POST /webhooks/whatsapp` |

## 9. Messaging rules enforced by the CRM

- **Free-form messages** (text and media) can only be sent within 24 hours of the customer's last inbound message.
- **Outside that window**, only Meta-approved templates can be sent.
- **No template, campaign or automation message goes to an opted-out contact.**
  - A customer is marked opted out when they reply with an opt-out keyword (default `STOP`, `UNSUBSCRIBE`) or tap the "Stop promotions" button.
  - Meta error 131050 also marks the contact opted out.
- **Campaigns and automated templates require consent.** They only go to contacts with consent "opted in". Having a phone number does not count as consent.
- **Sending is not guessed.** A message is saved, then sent to Meta, which returns a `wamid`; delivery, read and failure statuses then arrive through the webhook. If the call times out, the message is marked "unknown" and is never resent automatically.

## 10. Known limitations

- **Live updates use polling**, every 5 seconds while the tab is visible. The CRM has no WebSocket infrastructure.
- **Template creation in the CRM is limited.** It supports Utility and Marketing templates with a text header, body variables, a footer and an optional "Stop promotions" button. Media-header, authentication, carousel and flow templates must be created in WhatsApp Manager and then synced.
- **Interactive messages and reactions.** Incoming button/list replies, reactions, locations and contact cards are displayed. Sending interactive (button/list) messages is not offered in the composer.
- **Received media expires on Meta.** Received media is downloaded from Meta when first viewed and cached for the retention period. Meta keeps media for a limited time, so very old media may no longer be retrievable.
- **No cost figures.** Pricing and conversation costs are not shown; use WhatsApp Manager › Insights.
- **Lead and appointment triggers are not available.** The CRM has no lead or appointment models.
- **Automation notifications are email only.** The "notify staff" action uses Settings › Email (SMTP).
- **Two timezones.** Inbox times are shown in the browser's timezone. Other pages use the CRM timezone (Asia/Karachi).
