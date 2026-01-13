#!/usr/bin/env python3
"""
Initialize the unitMail local email database with sample data.

This script creates the database schema and populates it with 50 realistic
sample messages across different folders, with various states, attachments,
and thread relationships.
"""

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client.services.email_db import (
    EmailDatabase,
    Folder,
    Message,
    Attachment,
    Thread,
    FolderType,
    MessageStatus,
    MessagePriority,
)


# Sample data for generating realistic messages

SENDERS = [
    ("Alice Johnson", "alice.johnson@example.com"),
    ("Bob Smith", "bob.smith@company.org"),
    ("Sarah Williams", "sarah.williams@techcorp.io"),
    ("Mike Chen", "mike.chen@startup.co"),
    ("Lisa Anderson", "lisa.anderson@enterprise.com"),
    ("David Brown", "david.brown@university.edu"),
    ("Emily Davis", "emily.davis@agency.net"),
    ("James Wilson", "james.wilson@consulting.biz"),
    ("Maria Garcia", "maria.garcia@design.studio"),
    ("Tom Miller", "tom.miller@engineering.io"),
    ("Newsletter", "newsletter@updates.company.com"),
    ("HR Department", "hr@company.org"),
    ("Support Team", "support@service.help"),
    ("Project Team", "team@projectmanagement.io"),
    ("Finance Department", "finance@accounting.co"),
]

SUBJECTS = {
    "work": [
        "Q1 Project Planning Meeting",
        "Budget Review - Action Required",
        "New Feature Request from Client",
        "Code Review Feedback",
        "Sprint Retrospective Notes",
        "Weekly Status Update",
        "Important: System Maintenance Scheduled",
        "Team Lunch Friday",
        "Performance Review Meeting",
        "New Hire Onboarding",
        "Quarterly Goals Discussion",
        "Client Presentation Draft",
        "Infrastructure Upgrade Proposal",
        "Security Audit Results",
        "Training Session Next Week",
    ],
    "personal": [
        "Weekend Plans",
        "Birthday Party Invitation",
        "Photo Album from Trip",
        "Recipe You Asked For",
        "Book Recommendation",
        "Catching Up",
        "Family Reunion Details",
        "Movie Night Suggestion",
        "Apartment Hunting Update",
        "Concert Tickets Available",
    ],
    "newsletter": [
        "Weekly Tech Digest",
        "Your Monthly Summary",
        "New Features Announcement",
        "Industry News Roundup",
        "Product Update: Version 2.5 Released",
        "Best Practices Newsletter",
        "Community Spotlight",
        "Upcoming Events",
    ],
    "transactional": [
        "Order Confirmation #12345",
        "Your Receipt from Purchase",
        "Shipping Update: Package on the Way",
        "Password Reset Request",
        "Account Activity Alert",
        "Subscription Renewal Reminder",
        "Invoice for January Services",
        "Payment Confirmation",
    ],
}

BODY_TEMPLATES = {
    "work": [
        """Hi team,

I wanted to follow up on our discussion from last week. We need to finalize the project timeline and assign responsibilities.

Key points to address:
- Budget allocation for Q1
- Resource planning
- Milestone deadlines

Please review the attached document and let me know your thoughts by end of week.

Best regards,
{sender_name}""",
        """Hello,

As discussed in our meeting, I'm sharing the updated specifications for the new feature. Please review and provide feedback.

The main changes include:
1. Updated user interface design
2. New API endpoints
3. Performance optimizations

Let me know if you have any questions.

Thanks,
{sender_name}""",
        """Team,

Quick reminder about tomorrow's standup meeting at 10 AM. Please come prepared with:
- What you accomplished yesterday
- What you're working on today
- Any blockers

See you there!

{sender_name}""",
    ],
    "personal": [
        """Hey!

Hope you're doing well! Just wanted to check in and see how things are going.

We should catch up soon - maybe grab coffee this weekend?

Let me know what works for you!

{sender_name}""",
        """Hi there,

I came across this and thought of you immediately. Check out the link below - I think you'll really enjoy it!

Also, remember that thing we talked about? I have some updates to share when you have time.

Talk soon!
{sender_name}""",
    ],
    "newsletter": [
        """Hello {recipient_name},

Welcome to this week's newsletter! Here's what's new:

Featured Article: "10 Tips for Better Productivity"

Highlights:
- New feature release
- Community updates
- Upcoming webinar

Click here to read more on our website.

Best,
The Team""",
    ],
    "transactional": [
        """Dear Customer,

Thank you for your recent purchase. Your order has been confirmed.

Order Number: {order_num}
Total Amount: ${amount}

You will receive tracking information once your order ships.

Thank you for your business!

Customer Support Team""",
    ],
}

ATTACHMENT_SAMPLES = [
    ("report_q1_2026.pdf", "application/pdf", 245678),
    ("budget_spreadsheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 89432),
    ("presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", 1567890),
    ("meeting_notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 45678),
    ("project_timeline.png", "image/png", 234567),
    ("architecture_diagram.pdf", "application/pdf", 567890),
    ("contract_draft.pdf", "application/pdf", 123456),
    ("photo_001.jpg", "image/jpeg", 2345678),
    ("logo_final.svg", "image/svg+xml", 12345),
    ("data_export.csv", "text/csv", 456789),
    ("invoice_january.pdf", "application/pdf", 78901),
    ("screenshot.png", "image/png", 345678),
]


def create_system_folders(db: EmailDatabase) -> dict[str, str]:
    """Create system folders and return folder ID mapping."""
    folders_data = [
        ("inbox", "Inbox", FolderType.INBOX, "mail-inbox-symbolic", 0, True),
        ("sent", "Sent", FolderType.SENT, "mail-send-symbolic", 1, True),
        ("drafts", "Drafts", FolderType.DRAFTS, "mail-drafts-symbolic", 2, True),
        ("spam", "Spam", FolderType.SPAM, "mail-mark-junk-symbolic", 3, True),
        ("trash", "Trash", FolderType.TRASH, "user-trash-symbolic", 4, True),
        ("archive", "Archive", FolderType.ARCHIVE, "folder-symbolic", 5, True),
    ]

    folder_ids = {}
    for folder_id, name, folder_type, icon, sort_order, is_system in folders_data:
        folder = Folder(
            id=folder_id,
            name=name,
            folder_type=folder_type.value,
            icon_name=icon,
            sort_order=sort_order,
            is_system=is_system,
        )
        db.create_folder(folder)
        folder_ids[folder_id] = folder_id

    print(f"Created {len(folder_ids)} system folders")
    return folder_ids


def create_thread(db: EmailDatabase, subject: str, folder_id: str, participants: list[str]) -> Thread:
    """Create a thread for related messages."""
    thread = Thread(
        id=str(uuid4()),
        subject=subject,
        folder_id=folder_id,
        participant_addresses=participants,
    )
    return db.create_thread(thread)


def generate_message(
    folder_id: str,
    sender: tuple[str, str],
    subject: str,
    category: str,
    received_at: datetime,
    is_read: bool = False,
    is_starred: bool = False,
    thread_id: str = None,
    in_reply_to: str = None,
    has_attachment: bool = False,
) -> tuple[Message, list[Attachment]]:
    """Generate a message with optional attachments."""
    sender_name, sender_email = sender

    # Select body template
    templates = BODY_TEMPLATES.get(category, BODY_TEMPLATES["work"])
    body_template = random.choice(templates)

    body_text = body_template.format(
        sender_name=sender_name,
        recipient_name="User",
        order_num=random.randint(10000, 99999),
        amount=f"{random.randint(10, 500)}.{random.randint(0, 99):02d}",
    )

    # Create preview (first 100 chars)
    preview = body_text.replace("\n", " ").strip()[:150] + "..."

    message_id = str(uuid4())
    message = Message(
        id=message_id,
        folder_id=folder_id,
        thread_id=thread_id,
        message_id=f"<{uuid4()}@unitmail.local>",
        from_address=sender_email,
        to_addresses=["user@unitmail.local"],
        subject=subject,
        body_text=body_text,
        preview=preview,
        status=MessageStatus.RECEIVED.value,
        priority=random.choice([MessagePriority.NORMAL.value] * 8 + [MessagePriority.HIGH.value, MessagePriority.LOW.value]),
        is_read=is_read,
        is_starred=is_starred,
        in_reply_to=in_reply_to,
        received_at=received_at,
    )

    attachments = []
    if has_attachment:
        # Add 1-3 attachments
        num_attachments = random.randint(1, 3)
        selected_attachments = random.sample(ATTACHMENT_SAMPLES, min(num_attachments, len(ATTACHMENT_SAMPLES)))

        for filename, content_type, size in selected_attachments:
            attachment = Attachment(
                id=str(uuid4()),
                message_id=message_id,
                filename=filename,
                content_type=content_type,
                size=size,
            )
            attachments.append(attachment)

        message.has_attachments = True
        message.attachment_count = len(attachments)

    return message, attachments


def create_sample_messages(db: EmailDatabase, folder_ids: dict[str, str]) -> int:
    """Create 50 sample messages with realistic data."""
    messages_created = 0
    base_date = datetime.utcnow()

    # Create several thread conversations
    threads = []

    # Thread 1: Q1 Planning Discussion (5 messages)
    thread1_participants = [s[1] for s in SENDERS[:4]]
    thread1 = create_thread(db, "Q1 Project Planning Discussion", folder_ids["inbox"], thread1_participants)
    threads.append((thread1, "Q1 Project Planning Discussion", 5, "work"))

    # Thread 2: Code Review (3 messages)
    thread2_participants = [s[1] for s in [SENDERS[0], SENDERS[3], SENDERS[9]]]
    thread2 = create_thread(db, "Code Review: Feature Branch #123", folder_ids["inbox"], thread2_participants)
    threads.append((thread2, "Code Review: Feature Branch #123", 3, "work"))

    # Thread 3: Budget Review (4 messages)
    thread3_participants = [s[1] for s in [SENDERS[14], SENDERS[7], SENDERS[4]]]
    thread3 = create_thread(db, "Budget Review - Q1 Allocations", folder_ids["inbox"], thread3_participants)
    threads.append((thread3, "Budget Review - Q1 Allocations", 4, "work"))

    # Generate threaded messages
    for thread, subject, count, category in threads:
        prev_message_id = None
        for i in range(count):
            sender = random.choice(SENDERS[:10])
            received_at = base_date - timedelta(days=random.randint(0, 5), hours=random.randint(0, 23), minutes=random.randint(0, 59))

            reply_subject = subject if i == 0 else f"Re: {subject}"
            is_read = i < count - 2  # Last 2 messages unread
            is_starred = i == 0 and random.random() < 0.3  # Sometimes star first message
            has_attachment = i == 0 and random.random() < 0.4  # Sometimes attach to first

            message, attachments = generate_message(
                folder_id=folder_ids["inbox"],
                sender=sender,
                subject=reply_subject,
                category=category,
                received_at=received_at,
                is_read=is_read,
                is_starred=is_starred,
                thread_id=thread.id,
                in_reply_to=prev_message_id,
                has_attachment=has_attachment,
            )

            db.create_message(message)
            prev_message_id = message.message_id

            for attachment in attachments:
                db.create_attachment(attachment)

            messages_created += 1

        db.update_thread_counts(thread.id)

    # Individual inbox messages (20 messages)
    inbox_categories = ["work"] * 10 + ["personal"] * 4 + ["newsletter"] * 4 + ["transactional"] * 2
    random.shuffle(inbox_categories)

    for category in inbox_categories:
        sender = random.choice(SENDERS[:14] if category != "newsletter" else [SENDERS[10], SENDERS[13]])
        subjects = SUBJECTS.get(category, SUBJECTS["work"])
        subject = random.choice(subjects)

        received_at = base_date - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        is_read = random.random() < 0.6
        is_starred = random.random() < 0.15
        has_attachment = random.random() < 0.25

        message, attachments = generate_message(
            folder_id=folder_ids["inbox"],
            sender=sender,
            subject=subject,
            category=category,
            received_at=received_at,
            is_read=is_read,
            is_starred=is_starred,
            has_attachment=has_attachment,
        )

        db.create_message(message)
        for attachment in attachments:
            db.create_attachment(attachment)
        messages_created += 1

    # Sent folder messages (8 messages)
    for _ in range(8):
        recipient = random.choice(SENDERS[:10])
        subject = random.choice(SUBJECTS["work"] + SUBJECTS["personal"])
        sent_at = base_date - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))

        message = Message(
            id=str(uuid4()),
            folder_id=folder_ids["sent"],
            message_id=f"<{uuid4()}@unitmail.local>",
            from_address="user@unitmail.local",
            to_addresses=[recipient[1]],
            subject=subject,
            body_text=f"Hi {recipient[0].split()[0]},\n\n{random.choice(BODY_TEMPLATES['work']).format(sender_name='User', recipient_name=recipient[0].split()[0], order_num=12345, amount='0.00')}",
            preview=f"Hi {recipient[0].split()[0]}, ...",
            status=MessageStatus.SENT.value,
            is_read=True,
            sent_at=sent_at,
            received_at=sent_at,
        )

        db.create_message(message)
        messages_created += 1

    # Drafts (4 messages)
    for _ in range(4):
        subject = f"[Draft] {random.choice(SUBJECTS['work'])}"
        created_at = base_date - timedelta(days=random.randint(0, 7))

        message = Message(
            id=str(uuid4()),
            folder_id=folder_ids["drafts"],
            message_id=f"<{uuid4()}@unitmail.local>",
            from_address="user@unitmail.local",
            to_addresses=[],
            subject=subject,
            body_text="This is a draft message...\n\n[Content to be completed]",
            preview="This is a draft message...",
            status=MessageStatus.DRAFT.value,
            is_read=True,
            received_at=created_at,
        )

        db.create_message(message)
        messages_created += 1

    # Spam messages (5 messages)
    spam_senders = [
        ("Prince of Nigeria", "prince@totally-legit.ng"),
        ("Lottery Winner", "winner@lottery-fake.com"),
        ("Free Money", "cash@instant-rich.biz"),
        ("Hot Singles", "dating@spam-site.xyz"),
        ("Crypto Guru", "bitcoin@pump-dump.io"),
    ]
    spam_subjects = [
        "You've WON $5,000,000!!!",
        "Urgent: Your Account Needs Verification",
        "FREE Gift Card Inside!",
        "Hot Singles in Your Area Want to Meet",
        "Make $10,000/day from HOME!!!",
    ]

    for i in range(5):
        received_at = base_date - timedelta(days=random.randint(0, 10))

        message = Message(
            id=str(uuid4()),
            folder_id=folder_ids["spam"],
            message_id=f"<{uuid4()}@spam.local>",
            from_address=spam_senders[i][1],
            to_addresses=["user@unitmail.local"],
            subject=spam_subjects[i],
            body_text=f"CLICK HERE NOW to claim your prize! This is a limited time offer...\n\n{spam_senders[i][0]}",
            preview="CLICK HERE NOW to claim your prize!...",
            status=MessageStatus.RECEIVED.value,
            is_read=False,
            received_at=received_at,
        )

        db.create_message(message)
        messages_created += 1

    # Trash messages (3 messages)
    for _ in range(3):
        sender = random.choice(SENDERS)
        subject = f"[Deleted] {random.choice(SUBJECTS['work'])}"
        received_at = base_date - timedelta(days=random.randint(5, 30))

        message = Message(
            id=str(uuid4()),
            folder_id=folder_ids["trash"],
            message_id=f"<{uuid4()}@unitmail.local>",
            from_address=sender[1],
            to_addresses=["user@unitmail.local"],
            subject=subject,
            body_text="This message has been deleted.",
            preview="This message has been deleted.",
            status=MessageStatus.RECEIVED.value,
            is_read=True,
            received_at=received_at,
        )

        db.create_message(message)
        messages_created += 1

    # Archive messages (5 messages)
    for _ in range(5):
        sender = random.choice(SENDERS)
        subject = random.choice(SUBJECTS["work"])
        received_at = base_date - timedelta(days=random.randint(30, 180))

        message = Message(
            id=str(uuid4()),
            folder_id=folder_ids["archive"],
            message_id=f"<{uuid4()}@unitmail.local>",
            from_address=sender[1],
            to_addresses=["user@unitmail.local"],
            subject=subject,
            body_text=random.choice(BODY_TEMPLATES["work"]).format(
                sender_name=sender[0], recipient_name="User", order_num=12345, amount="0.00"
            ),
            preview="This is an archived message...",
            status=MessageStatus.RECEIVED.value,
            is_read=True,
            is_starred=random.random() < 0.2,
            received_at=received_at,
        )

        db.create_message(message)
        messages_created += 1

    return messages_created


def main():
    """Main entry point for database initialization."""
    print("=" * 60)
    print("unitMail Local Email Database Initialization")
    print("=" * 60)
    print()

    # Initialize database
    db = EmailDatabase()
    print(f"Database location: {db.db_path}")
    print()

    # Check if database already exists with data
    if db.db_path.exists():
        db.initialize()
        stats = db.get_stats()
        if stats["messages"] > 0:
            print(f"Database already contains {stats['messages']} messages.")
            response = input("Do you want to reset and recreate? (y/N): ")
            if response.lower() != 'y':
                print("Keeping existing database.")
                print()
                print("Current statistics:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
                return

            # Delete existing database
            db.db_path.unlink()
            print("Existing database deleted.")

    # Initialize fresh database
    db.initialize()
    print("Database schema created.")
    print()

    # Create folders
    print("Creating system folders...")
    folder_ids = create_system_folders(db)
    print()

    # Create sample messages
    print("Creating sample messages...")
    message_count = create_sample_messages(db, folder_ids)
    print(f"Created {message_count} sample messages.")
    print()

    # Update all folder counts
    print("Updating folder counts...")
    for folder_id in folder_ids.values():
        db.update_folder_counts(folder_id)

    # Print final statistics
    print()
    print("=" * 60)
    print("Database Initialization Complete")
    print("=" * 60)
    stats = db.get_stats()
    print()
    print("Statistics:")
    print(f"  Folders: {stats['folders']}")
    print(f"  Messages: {stats['messages']}")
    print(f"  Unread: {stats['unread']}")
    print(f"  Starred: {stats['starred']}")
    print(f"  Threads: {stats['threads']}")
    print(f"  Attachments: {stats['attachments']}")
    print(f"  Database size: {stats['database_size_bytes'] / 1024:.2f} KB")
    print()
    print(f"Database saved to: {stats['database_path']}")


if __name__ == "__main__":
    main()
