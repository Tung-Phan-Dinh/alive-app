# Testing the Trigger System

## Prerequisites

1. API running locally: `uvicorn app.main:app --reload`
2. MySQL database with migrations applied
3. `.env` configured (set `EMAIL_USE_CONSOLE=true` for testing)

## Test Plan

### 1. Create a Test User with Past Deadline

```bash
# Login/create a dev user
curl -X POST http://localhost:8000/api/v1/auth/dev \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Save the access_token from the response
export TOKEN="your-access-token-here"
```

### 2. Add Emergency Contacts

```bash
# Add a contact with email
curl -X POST http://localhost:8000/api/v1/contacts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emergency Contact",
    "email": "contact@example.com",
    "death_message": "Hey, I haven'\''t checked in. Please check on me!"
  }'
```

### 3. Set User's Last Active to the Past (via MySQL)

```sql
-- Set last_active_at to 50 hours ago (past the 48-hour default deadline)
UPDATE users
SET last_active_at = DATE_SUB(NOW(), INTERVAL 50 HOUR)
WHERE email = 'test@example.com';

-- Verify
SELECT id, email, last_active_at, checkin_period_hours, is_dead
FROM users
WHERE email = 'test@example.com';
```

### 4. Run the Trigger Worker Manually

```bash
cd /path/to/alive-api
source alive_venv/bin/activate
python -m app.worker.trigger_worker
```

Expected output:
```
Starting trigger check...
Found 1 triggered users to process
Created trigger event 1 for user 1
EMAIL TO: contact@example.com
SUBJECT: Emergency Alert: test@example.com has not checked in
[... email body ...]
Sent notification to contact@example.com for user 1
Trigger check complete in 0.12s - Users: 1, Emails sent: 1, Emails failed: 0
```

### 5. Verify Database State

```sql
-- Check user is marked as dead
SELECT id, email, is_dead FROM users WHERE email = 'test@example.com';
-- Should show: is_dead = 1

-- Check trigger event was created
SELECT * FROM trigger_events WHERE user_id = (SELECT id FROM users WHERE email = 'test@example.com');
-- Should show: status = 'triggered', resolved_at = NULL

-- Check notification was recorded
SELECT n.*, c.name, c.email as contact_email
FROM notifications n
JOIN contacts c ON n.contact_id = c.id
WHERE n.trigger_event_id = 1;
-- Should show: status = 'sent', sent_at = [timestamp]
```

### 6. Verify No Duplicate Sends

```bash
# Run the worker again
python -m app.worker.trigger_worker
```

Expected output:
```
Starting trigger check...
Trigger check complete in 0.02s - Users: 0, Emails sent: 0, Emails failed: 0
```

No emails should be sent because:
- User already has an active trigger event
- User is already marked as dead

### 7. Test Resurrection (User Checks In)

```bash
# User checks in
curl -X POST http://localhost:8000/api/v1/check-in \
  -H "Authorization: Bearer $TOKEN"
```

Expected response includes:
```json
{
  "success": true,
  "message": "Welcome back! You've been resurrected.",
  "resurrected": true,
  ...
}
```

### 8. Verify Resurrection in Database

```sql
-- User should no longer be dead
SELECT id, email, is_dead, last_active_at FROM users WHERE email = 'test@example.com';
-- Should show: is_dead = 0, last_active_at = [recent timestamp]

-- Trigger event should be resolved
SELECT * FROM trigger_events WHERE user_id = (SELECT id FROM users WHERE email = 'test@example.com');
-- Should show: status = 'resolved', resolved_at = [timestamp]
```

### 9. Test Re-trigger After Resurrection

```sql
-- Set last_active to past again
UPDATE users
SET last_active_at = DATE_SUB(NOW(), INTERVAL 50 HOUR)
WHERE email = 'test@example.com';
```

```bash
# Run worker - should trigger again
python -m app.worker.trigger_worker
```

A NEW trigger event and notifications should be created because the previous one was resolved.

## Testing with Real Emails

1. Set `EMAIL_USE_CONSOLE=false` in `.env`
2. Configure real SMTP credentials
3. Use a real email address for the contact
4. Run the worker and check your inbox

## Common Issues

### "No triggered users found"
- Check `last_active_at` is set and in the past
- Check `is_dead` is not already `1`
- Check there's no active trigger event for the user

### "0 emails sent but user processed"
- Contact might not have an email address
- Check `contacts` table has valid emails

### "SMTP authentication failed"
- For Gmail: Use App Password, not regular password
- Check `SMTP_USER` matches `EMAIL_FROM`

### Duplicate constraint error
- This is expected if running worker twice quickly
- The INSERT ON DUPLICATE KEY handles this gracefully
