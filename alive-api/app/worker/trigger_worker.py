#!/usr/bin/env python3
"""
Trigger Worker - Detects missed check-ins and sends emergency contact emails.

This script is designed to be run periodically via systemd timer (every minute).
It is idempotent and safe to run concurrently (uses DB-level uniqueness constraints).

Usage:
    python -m app.worker.trigger_worker

Or directly:
    ./app/worker/trigger_worker.py
"""
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert as mysql_insert

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import User, Contact, TriggerEvent, Notification
from app.services.email_client import (
    create_email_client,
    EmailMessage,
    EmailClient,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("trigger_worker")


DEFAULT_DEATH_MESSAGE = """
This is an automated message from the Alive App.

The person who added you as an emergency contact has not checked in within their specified time period.

This may indicate they need assistance. Please try to reach them or check on their wellbeing.

If you believe this is an error, they may have simply forgotten to check in.
"""


def build_email_body(user: User, contact: Contact) -> tuple[str, str]:
    """
    Build email body (text and HTML) for a death notification.
    Returns (text_body, html_body).
    """
    message = contact.death_message or DEFAULT_DEATH_MESSAGE

    text_body = f"""Emergency Alert from Alive App

Contact Name: {contact.name}

{message.strip()}

---
This message was sent by the Alive App on behalf of {user.email}.
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
        .message {{ background: white; padding: 15px; border-left: 4px solid #dc3545; margin: 15px 0; }}
        .footer {{ font-size: 12px; color: #666; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Emergency Alert</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{contact.name}</strong>,</p>
            <div class="message">
                {message.strip().replace(chr(10), '<br>')}
            </div>
            <div class="footer">
                <p>This message was sent by the Alive App on behalf of {user.email}.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return text_body, html_body


async def find_triggered_users(db: AsyncSession, batch_size: int = 50) -> List[User]:
    """
    Find users who have missed their check-in deadline and don't have
    an active (unresolved) trigger event.
    """
    now = datetime.now(timezone.utc)

    # Subquery: users with active trigger events
    active_trigger_subq = (
        select(TriggerEvent.user_id)
        .where(TriggerEvent.status == "triggered")
        .scalar_subquery()
    )

    # Main query: users past deadline without active trigger
    query = (
        select(User)
        .where(
            and_(
                User.last_active_at.isnot(None),
                User.is_dead == False,  # Not already marked dead
                User.id.notin_(active_trigger_subq),  # No active trigger event
            )
        )
        .limit(batch_size)
    )

    result = await db.execute(query)
    users = result.scalars().all()

    # Filter in Python for deadline check (MySQL datetime math is tricky with timezones)
    triggered_users = []
    for user in users:
        if user.last_active_at:
            last_active_utc = user.last_active_at.replace(tzinfo=timezone.utc)
            deadline = last_active_utc + timedelta(hours=user.checkin_period_hours)
            if now > deadline:
                triggered_users.append(user)

    return triggered_users


async def get_contacts_with_email(db: AsyncSession, user_id: int) -> List[Contact]:
    """Get all contacts for a user that have valid email addresses."""
    query = (
        select(Contact)
        .where(
            and_(
                Contact.user_id == user_id,
                Contact.email.isnot(None),
                Contact.email != "",
            )
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_trigger_event(db: AsyncSession, user: User) -> Optional[TriggerEvent]:
    """
    Create a trigger event for a user.
    Returns the event if created, None if one already exists (race condition).
    """
    now = datetime.now(timezone.utc)
    last_active_utc = user.last_active_at.replace(tzinfo=timezone.utc)
    deadline = last_active_utc + timedelta(hours=user.checkin_period_hours)

    event = TriggerEvent(
        user_id=user.id,
        triggered_at=now,
        deadline_at=deadline,
        status="triggered",
    )
    db.add(event)

    try:
        await db.flush()
        return event
    except Exception as e:
        logger.warning(f"Failed to create trigger event for user {user.id}: {e}")
        await db.rollback()
        return None


async def create_notification_record(
    db: AsyncSession,
    trigger_event_id: int,
    contact: Contact,
) -> Optional[Notification]:
    """
    Create a notification record. Uses INSERT IGNORE to handle duplicates.
    Returns the notification if created, None if duplicate.
    """
    # Use MySQL INSERT ... ON DUPLICATE KEY to handle race conditions
    stmt = mysql_insert(Notification).values(
        trigger_event_id=trigger_event_id,
        contact_id=contact.id,
        channel="email",
        recipient_address=contact.email,
        status="pending",
    )
    # On duplicate, do nothing (just ignore)
    stmt = stmt.on_duplicate_key_update(
        status=stmt.inserted.status  # No-op update
    )

    try:
        result = await db.execute(stmt)
        await db.flush()

        # Check if we inserted or it was a duplicate
        if result.rowcount > 0:
            # Fetch the created notification
            query = select(Notification).where(
                and_(
                    Notification.trigger_event_id == trigger_event_id,
                    Notification.contact_id == contact.id,
                    Notification.channel == "email",
                )
            )
            notif_result = await db.execute(query)
            return notif_result.scalar_one_or_none()
        return None
    except Exception as e:
        logger.warning(f"Failed to create notification for contact {contact.id}: {e}")
        return None


async def send_notification(
    db: AsyncSession,
    email_client: EmailClient,
    notification: Notification,
    user: User,
    contact: Contact,
) -> bool:
    """Send an email notification and update the DB record."""
    text_body, html_body = build_email_body(user, contact)

    message = EmailMessage(
        to=contact.email,
        subject=f"Emergency Alert: {user.email} has not checked in",
        body_text=text_body,
        body_html=html_body,
    )

    result = await email_client.send(message)
    now = datetime.now(timezone.utc)

    if result.success:
        notification.status = "sent"
        notification.sent_at = now
        notification.error_text = None
        logger.info(f"Sent notification to {contact.email} for user {user.id}")
    else:
        notification.status = "failed"
        notification.error_text = result.error[:500] if result.error else "Unknown error"
        notification.retry_count += 1
        logger.error(f"Failed to send to {contact.email}: {result.error}")

    notification.updated_at = now
    await db.flush()
    return result.success


async def process_user(
    db: AsyncSession,
    email_client: EmailClient,
    user: User,
    email_delay: float,
) -> dict:
    """
    Process a single triggered user:
    1. Create trigger event
    2. Load contacts
    3. Create notification records
    4. Send emails
    5. Mark user as dead

    Returns stats dict.
    """
    stats = {"emails_sent": 0, "emails_failed": 0, "contacts_skipped": 0}

    # Create trigger event
    event = await create_trigger_event(db, user)
    if not event:
        logger.info(f"Skipping user {user.id} - trigger event already exists")
        return stats

    logger.info(f"Created trigger event {event.id} for user {user.id}")

    # Get contacts with email
    contacts = await get_contacts_with_email(db, user.id)
    if not contacts:
        logger.info(f"User {user.id} has no contacts with email - marking as dead anyway")
        user.is_dead = True
        await db.commit()
        return stats

    # Process each contact
    for contact in contacts:
        # Create notification record
        notification = await create_notification_record(db, event.id, contact)
        if not notification:
            stats["contacts_skipped"] += 1
            continue

        # Send email
        success = await send_notification(db, email_client, notification, user, contact)
        if success:
            stats["emails_sent"] += 1
        else:
            stats["emails_failed"] += 1

        # Rate limiting delay
        if email_delay > 0:
            await asyncio.sleep(email_delay)

    # Mark user as dead
    user.is_dead = True
    await db.commit()

    return stats


async def run_trigger_check():
    """Main worker function - find and process all triggered users."""
    start_time = time.time()
    logger.info("Starting trigger check...")

    # Create email client
    email_client = create_email_client(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        from_address=settings.EMAIL_FROM,
        from_name=settings.EMAIL_FROM_NAME,
        use_console=settings.EMAIL_USE_CONSOLE,
    )

    total_stats = {"users_processed": 0, "emails_sent": 0, "emails_failed": 0}

    try:
        async with SessionLocal() as db:
            # Find triggered users in batches
            while True:
                users = await find_triggered_users(db, settings.WORKER_BATCH_SIZE)
                if not users:
                    break

                logger.info(f"Found {len(users)} triggered users to process")

                for user in users:
                    try:
                        stats = await process_user(
                            db,
                            email_client,
                            user,
                            settings.WORKER_EMAIL_DELAY_SECONDS,
                        )
                        total_stats["users_processed"] += 1
                        total_stats["emails_sent"] += stats["emails_sent"]
                        total_stats["emails_failed"] += stats["emails_failed"]
                    except Exception as e:
                        logger.exception(f"Error processing user {user.id}: {e}")
                        await db.rollback()

    finally:
        email_client.close()

    elapsed = time.time() - start_time
    logger.info(
        f"Trigger check complete in {elapsed:.2f}s - "
        f"Users: {total_stats['users_processed']}, "
        f"Emails sent: {total_stats['emails_sent']}, "
        f"Emails failed: {total_stats['emails_failed']}"
    )

    return total_stats


async def retry_failed_notifications():
    """
    Retry failed notifications (optional - can be run separately).
    Only retries notifications that failed less than 3 times.
    """
    logger.info("Checking for failed notifications to retry...")

    email_client = create_email_client(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        from_address=settings.EMAIL_FROM,
        from_name=settings.EMAIL_FROM_NAME,
        use_console=settings.EMAIL_USE_CONSOLE,
    )

    retried = 0
    try:
        async with SessionLocal() as db:
            # Find failed notifications with retry_count < 3
            query = (
                select(Notification)
                .where(
                    and_(
                        Notification.status == "failed",
                        Notification.retry_count < 3,
                    )
                )
                .limit(20)
            )
            result = await db.execute(query)
            notifications = list(result.scalars().all())

            for notif in notifications:
                # Load related objects
                contact_result = await db.execute(
                    select(Contact).where(Contact.id == notif.contact_id)
                )
                contact = contact_result.scalar_one_or_none()
                if not contact:
                    continue

                event_result = await db.execute(
                    select(TriggerEvent).where(TriggerEvent.id == notif.trigger_event_id)
                )
                event = event_result.scalar_one_or_none()
                if not event or event.status == "resolved":
                    continue

                user_result = await db.execute(
                    select(User).where(User.id == event.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                # Retry send
                await send_notification(db, email_client, notif, user, contact)
                retried += 1

                await asyncio.sleep(settings.WORKER_EMAIL_DELAY_SECONDS)

            await db.commit()

    finally:
        email_client.close()

    logger.info(f"Retried {retried} failed notifications")


async def main():
    """Entry point for the worker."""
    await run_trigger_check()
    await retry_failed_notifications()


if __name__ == "__main__":
    asyncio.run(main())
