"""
Sample Data Generator for unitMail.

This module generates realistic sample email messages for testing
and development purposes. Creates 50+ messages across all folders
with threads, attachments, and various states.
"""

import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .storage import get_storage
from .storage.schema import MessagePriority, MessageStatus


# Sample people for email conversations
CONTACTS = [
    {"name": "Alice Johnson", "email": "alice.johnson@techcorp.com"},
    {"name": "Bob Smith", "email": "bob.smith@startup.io"},
    {"name": "Carol Davis", "email": "carol.davis@design.co"},
    {"name": "David Wilson", "email": "david.wilson@finance.net"},
    {"name": "Eve Martinez", "email": "eve.martinez@marketing.biz"},
    {"name": "Frank Brown", "email": "frank.brown@engineering.dev"},
    {"name": "Grace Lee", "email": "grace.lee@hr.company.com"},
    {"name": "Henry Taylor", "email": "henry.taylor@sales.org"},
    {"name": "Iris Chen", "email": "iris.chen@research.edu"},
    {"name": "Jack Anderson", "email": "jack.anderson@support.help"},
    {"name": "Karen White", "email": "karen.white@legal.law"},
    {"name": "Leo Garcia", "email": "leo.garcia@product.team"},
    {"name": "Maya Patel", "email": "maya.patel@operations.co"},
    {"name": "Nathan Kim", "email": "nathan.kim@analytics.data"},
    {"name": "Olivia Robinson", "email": "olivia.robinson@creative.studio"},
]

# Current user
ME = {"name": "You", "email": "me@unitmail.local"}


def generate_sample_messages(force_regenerate: bool = False) -> int:
    """
    Generate 50+ sample messages with threads and attachments.

    Args:
        force_regenerate: If True, clears existing messages first.

    Returns:
        Number of messages created.
    """
    storage = get_storage()

    # Check if messages already exist (quick check with limit=1)
    if not force_regenerate and len(storage.get_all_messages(limit=1)) > 0:
        # Return actual total count
        return len(storage.get_all_messages())

    if force_regenerate:
        # Clear all messages
        for msg in storage.get_all_messages(limit=10000):
            storage.delete_message(msg["id"])

    folders = storage.get_folders()
    inbox_id = next((f["id"] for f in folders if f["name"] == "Inbox"), None)
    sent_id = next((f["id"] for f in folders if f["name"] == "Sent"), None)
    drafts_id = next((f["id"] for f in folders if f["name"] == "Drafts"), None)
    trash_id = next((f["id"] for f in folders if f["name"] == "Trash"), None)
    spam_id = next((f["id"] for f in folders if f["name"] == "Spam"), None)
    archive_id = next((f["id"]
                      for f in folders if f["name"] == "Archive"), None)

    if not inbox_id:
        raise RuntimeError(
            "Inbox folder not found - ensure storage is initialized")

    messages_created = 0
    base_time = datetime.now(timezone.utc)

    # Thread 1: Project Planning (5 messages in Inbox)
    thread1_id = str(uuid4())
    thread1_messages = [
        {
            "from": CONTACTS[0],
            "subject": "Q1 Project Planning Meeting",
            "body_text": """Hi team,

I wanted to schedule a meeting to discuss our Q1 project planning. We have several initiatives to review and prioritize.

Key topics:
- Budget allocation for new features
- Resource planning
- Timeline estimates
- Risk assessment

Please let me know your availability for next week.

Best,
Alice""",
            "hours_ago": 48,
            "attachments": [{"filename": "Q1_roadmap.pdf", "size": 245000, "content_type": "application/pdf"}],
            "is_read": True,
        },
        {
            "from": CONTACTS[1],
            "subject": "Re: Q1 Project Planning Meeting",
            "body_text": """Hi Alice,

Thanks for organizing this. I'm available:
- Tuesday 2-4pm
- Wednesday 10am-12pm
- Thursday any time after 1pm

I've been working on the technical specs for the new API. Should I present those during the meeting?

Bob""",
            "hours_ago": 46,
            "is_read": True,
        },
        {
            "from": CONTACTS[2],
            "subject": "Re: Q1 Project Planning Meeting",
            "body_text": """Adding my availability:
- Tuesday 2-4pm works for me too
- Wednesday I have client calls

Carol

P.S. I'll bring the updated mockups for the dashboard redesign.""",
            "hours_ago": 44,
            "is_read": True,
        },
        {
            "from": CONTACTS[0],
            "subject": "Re: Q1 Project Planning Meeting",
            "body_text": """Great! Let's do Tuesday 2-4pm then.

I've booked Conference Room A. I'll send calendar invites shortly.

@Bob - yes, please prepare the API specs presentation
@Carol - looking forward to seeing the mockups!

Alice""",
            "hours_ago": 42,
            "attachments": [{"filename": "meeting_agenda.docx", "size": 45000, "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}],
            "is_read": True,
        },
        {
            "from": CONTACTS[1],
            "subject": "Re: Q1 Project Planning Meeting",
            "body_text": """Perfect, see everyone Tuesday!

I'll have the slides ready. Quick question - should I include the performance benchmarks from last quarter?

Bob""",
            "hours_ago": 40,
            "is_read": False,
            "is_starred": True,
        },
    ]

    for msg_data in thread1_messages:
        storage.create_message({
            "folder_id": inbox_id,
            "from_address": msg_data["from"]["email"],
            "to_addresses": [ME["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": msg_data.get("is_read", False),
            "is_starred": msg_data.get("is_starred", False),
            "attachments": msg_data.get("attachments", []),
            "thread_id": thread1_id,
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
        })
        messages_created += 1

    # Thread 2: Bug Report (4 messages - urgent)
    thread2_id = str(uuid4())
    thread2_messages = [
        {
            "from": CONTACTS[9],
            "subject": "Critical Bug: Login Failure on Mobile",
            "body_text": """URGENT: We're receiving multiple reports of login failures on mobile devices.

Affected:
- iOS Safari
- Android Chrome

Steps to reproduce:
1. Open app on mobile browser
2. Enter valid credentials
3. Click Login
4. Error: "Authentication timeout"

This is blocking several users. Please investigate ASAP.

Jack - Support Team""",
            "hours_ago": 12,
            "priority": MessagePriority.URGENT.value,
            "is_read": True,
        },
        {
            "from": CONTACTS[5],
            "subject": "Re: Critical Bug: Login Failure on Mobile",
            "body_text": """I'm looking into this now.

Initial findings: The issue appears to be related to the session token timeout being too aggressive on mobile networks with higher latency.

I'm pushing a hotfix to increase the timeout from 5s to 15s.

ETA: 30 minutes for staging, 1 hour for production.

Frank""",
            "hours_ago": 11,
            "is_read": True,
        },
        {
            "from": CONTACTS[9],
            "subject": "Re: Critical Bug: Login Failure on Mobile",
            "body_text": """Thanks Frank! I'll let the affected users know we're working on it.

Can you also add better error messaging? "Authentication timeout" isn't very helpful for users.

Jack""",
            "hours_ago": 10,
            "is_read": True,
        },
        {
            "from": CONTACTS[5],
            "subject": "Re: Critical Bug: Login Failure on Mobile",
            "body_text": """Good point. I've updated the error message to:

"Connection is taking longer than expected. Please check your internet connection and try again."

Fix is now live in production. Please test and confirm.

Frank""",
            "hours_ago": 8,
            "is_read": False,
            "attachments": [{"filename": "fix_details.txt", "size": 2400, "content_type": "text/plain"}],
        },
    ]

    for msg_data in thread2_messages:
        storage.create_message({
            "folder_id": inbox_id,
            "from_address": msg_data["from"]["email"],
            "to_addresses": [ME["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": msg_data.get("is_read", False),
            "is_starred": msg_data.get("is_starred", False),
            "priority": msg_data.get("priority", MessagePriority.NORMAL.value),
            "attachments": msg_data.get("attachments", []),
            "thread_id": thread2_id,
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
        })
        messages_created += 1

    # Individual inbox messages
    individual_messages = [
        {
            "from": CONTACTS[3],
            "subject": "Budget Approval Request",
            "body_text": """Hi,

Please review and approve the attached budget proposal for the Q1 infrastructure upgrade.

Key points:
- Total cost: $45,000
- Timeline: 6 weeks
- ROI expected: 25% efficiency improvement

Let me know if you have any questions.

David - Finance""",
            "hours_ago": 2,
            "is_read": False,
            "priority": MessagePriority.HIGH.value,
            "attachments": [
                {"filename": "budget_proposal_q1.xlsx", "size": 125000,
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                {"filename": "infrastructure_plan.pdf",
                    "size": 890000, "content_type": "application/pdf"},
            ],
        },
        {
            "from": CONTACTS[6],
            "subject": "Updated PTO Policy",
            "body_text": """Dear Team,

Please find attached the updated PTO policy effective February 1st.

Key changes:
- Increased annual PTO from 15 to 20 days
- New mental health day allowance (3 days/year)
- Simplified approval process for requests under 3 days

Please review and acknowledge by clicking the link below.

Best regards,
Grace - HR""",
            "hours_ago": 4,
            "is_read": True,
            "attachments": [{"filename": "PTO_Policy_2026.pdf", "size": 340000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[8],
            "subject": "Research Paper: Machine Learning in Email Classification",
            "body_text": """Hello,

I came across this fascinating research paper on ML-based email classification that might be relevant to our spam filter improvements.

The paper presents a novel approach using transformer architectures that achieved 99.2% accuracy on the benchmark dataset.

I've attached the paper and my summary notes.

Let me know if you'd like to discuss potential applications.

Iris - Research""",
            "hours_ago": 6,
            "is_read": False,
            "is_starred": True,
            "attachments": [
                {"filename": "ml_email_classification.pdf",
                    "size": 2450000, "content_type": "application/pdf"},
                {"filename": "summary_notes.md", "size": 8500,
                    "content_type": "text/markdown"},
            ],
        },
        {
            "from": CONTACTS[7],
            "subject": "Sales Forecast Q1 2026",
            "body_text": """Team,

Here's the Q1 sales forecast based on our current pipeline:

- January: $120K (confirmed)
- February: $95K (projected)
- March: $150K (projected)

Total Q1 Projection: $365K

We're tracking 15% above last year. The new enterprise deals are looking promising.

Full breakdown attached.

Henry - Sales""",
            "hours_ago": 8,
            "is_read": True,
            "attachments": [{"filename": "Q1_Forecast_2026.xlsx", "size": 78000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}],
        },
        {
            "from": CONTACTS[10],
            "subject": "Legal Review: Terms of Service Update",
            "body_text": """Hi,

I've completed the legal review of the proposed Terms of Service updates. Please find my comments in the attached document.

Key concerns:
1. Data retention clause needs clarification
2. Liability limitations may need regional adjustments
3. GDPR compliance language should be strengthened

Let's schedule a call to discuss before we publish.

Karen - Legal""",
            "hours_ago": 10,
            "is_read": False,
            "priority": MessagePriority.HIGH.value,
            "attachments": [{"filename": "ToS_Review_Comments.docx", "size": 156000, "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}],
        },
        {
            "from": CONTACTS[12],
            "subject": "Server Maintenance Window",
            "body_text": """Team,

Scheduled maintenance window:
- Date: Saturday, January 18th
- Time: 2:00 AM - 6:00 AM UTC
- Expected downtime: 30 minutes

What we're doing:
- Database migration to new cluster
- Security patches
- Performance optimizations

Status page will be updated throughout.

Maya - Operations""",
            "hours_ago": 14,
            "is_read": True,
        },
        {
            "from": CONTACTS[13],
            "subject": "User Engagement Report - December 2025",
            "body_text": """Hi team,

December metrics are in! Highlights:

Active Users: +12% MoM
Avg Session Duration: 8.5 minutes (+2.1 min)
Feature Adoption: Dashboard widgets at 78%
Mobile Usage: 34% of total traffic

Full report attached with detailed breakdowns by region and feature.

Nathan - Analytics""",
            "hours_ago": 18,
            "is_read": True,
            "attachments": [{"filename": "Engagement_Report_Dec2025.pdf", "size": 1250000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[14],
            "subject": "Brand Guidelines Update",
            "body_text": """Hello everyone,

I've updated our brand guidelines to reflect the recent logo refresh. Key changes:

- New primary color palette
- Updated typography system
- Revised logo usage rules
- New iconography style

Please download the latest assets from the shared drive.

Olivia - Creative""",
            "hours_ago": 22,
            "is_read": True,
            "attachments": [
                {"filename": "Brand_Guidelines_v3.pdf",
                    "size": 5400000, "content_type": "application/pdf"},
                {"filename": "Logo_Pack.zip", "size": 12500000,
                    "content_type": "application/zip"},
            ],
        },
        {
            "from": CONTACTS[0],
            "subject": "API Documentation Review Request",
            "body_text": """Hi,

Could you review the API documentation I've been working on? I want to make sure it's accurate and easy to understand before we publish.

Focus areas:
- Authentication flow
- Rate limiting explanation
- Error codes and handling
- Code examples

Link: docs.example.com/api/v2/preview

Thanks!
Alice""",
            "hours_ago": 26,
            "is_read": False,
        },
        {
            "from": CONTACTS[1],
            "subject": "Code Review: Feature Branch #234",
            "body_text": """Hey,

I've pushed the feature branch for the new notification system. Could you take a look when you have a chance?

PR: github.com/unitmail/core/pull/234

Changes:
- New notification service
- WebSocket integration
- User preference settings
- Unit tests (92% coverage)

Let me know if you see any issues.

Bob""",
            "hours_ago": 30,
            "is_read": False,
            "is_starred": True,
        },
        {
            "from": CONTACTS[9],
            "subject": "Support Ticket Escalation - Priority Customer",
            "body_text": """ESCALATION

Ticket: #45678
Customer: TechGiant Inc (Enterprise)
Issue: Data export failing for accounts > 100GB
Impact: High - blocking their migration

They've been waiting 48 hours. This needs immediate attention.

Jack - Support""",
            "hours_ago": 1,
            "is_read": False,
            "priority": MessagePriority.URGENT.value,
        },
        {
            "from": CONTACTS[11],
            "subject": "Feature Request Analysis",
            "body_text": """Based on user feedback analysis, here are the top 5 requested features:

1. Dark mode (847 requests)
2. Keyboard shortcuts (623 requests)
3. Custom filters (512 requests)
4. Calendar integration (489 requests)
5. Mobile app (445 requests)

I've created detailed specs for each. Let's discuss prioritization.

Leo - Product""",
            "hours_ago": 70,
            "is_read": True,
            "is_starred": True,
            "attachments": [{"filename": "Feature_Specs.pdf", "size": 890000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[6],
            "subject": "Team Offsite Planning",
            "body_text": """Hi everyone,

We're planning a team offsite for Q2. Please fill out the survey to help us choose:
- Dates that work for you
- Location preferences
- Activity interests

Survey link: forms.company.com/offsite-2026

Deadline: January 25th

Grace - HR""",
            "hours_ago": 15,
            "is_read": False,
            "attachments": [{"filename": "offsite_proposals.pdf", "size": 670000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[4],
            "subject": "Newsletter Content Ideas for February",
            "body_text": """Hi team,

It's time to plan our February newsletter! Here are some content ideas:

1. Product Update: New dashboard features
2. Customer Success Story: Acme Corp case study
3. Industry News: Latest trends in our space
4. Tips & Tricks: Getting the most out of our platform

I'd love to hear your suggestions. Deadline for content is Feb 1st.

Eve - Marketing""",
            "hours_ago": 72,
            "is_read": True,
        },
    ]

    for msg_data in individual_messages:
        storage.create_message({
            "folder_id": inbox_id,
            "from_address": msg_data["from"]["email"],
            "to_addresses": [ME["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": msg_data.get("is_read", False),
            "is_starred": msg_data.get("is_starred", False),
            "priority": msg_data.get("priority", MessagePriority.NORMAL.value),
            "attachments": msg_data.get("attachments", []),
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
        })
        messages_created += 1

    # Sent messages (5 messages)
    sent_messages = [
        {
            "to": CONTACTS[0],
            "subject": "Re: API Documentation Review Request",
            "body_text": """Hi Alice,

I've reviewed the documentation. Looks great overall!

A few suggestions:
1. Add example responses for error codes
2. Include curl examples alongside code snippets
3. The auth section could use a sequence diagram

Let me know if you want me to make these edits directly.

Best""",
            "hours_ago": 24,
        },
        {
            "to": CONTACTS[5],
            "subject": "Re: Database Migration Plan",
            "body_text": """Frank,

The plan looks solid. One question - what's our rollback time if we hit issues in Phase 2?

Also, should we do a dry run in staging first?

Thanks""",
            "hours_ago": 48,
        },
        {
            "to": CONTACTS[9],
            "subject": "Re: Support Ticket Escalation - Priority Customer",
            "body_text": """Jack,

I'm looking into this now. Can you get me:
1. Account ID
2. Specific error messages they're seeing
3. When did this start happening?

I'll prioritize this today.

Thanks""",
            "hours_ago": 0.5,
        },
        {
            "to": CONTACTS[11],
            "subject": "Re: Feature Request Analysis",
            "body_text": """Leo,

Great analysis! I agree dark mode and keyboard shortcuts should be top priority.

For calendar integration - are users asking for Google Calendar specifically or any calendar?

Let's discuss in our next product sync.

Thanks""",
            "hours_ago": 68,
        },
        {
            "to": CONTACTS[3],
            "subject": "Budget Approval - Confirmed",
            "body_text": """David,

Budget approved! Proceed with the infrastructure upgrade.

Please send weekly progress updates and flag any blockers immediately.

Thanks""",
            "hours_ago": 1.5,
        },
    ]

    if sent_id:
        for msg_data in sent_messages:
            storage.create_message({
                "folder_id": sent_id,
                "from_address": ME["email"],
                "to_addresses": [msg_data["to"]["email"]],
                "subject": msg_data["subject"],
                "body_text": msg_data["body_text"],
                "is_read": True,
                "status": MessageStatus.SENT.value,
                "sent_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
                "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
                "headers": {"To": f"{msg_data['to']['name']} <{msg_data['to']['email']}>"},
            })
            messages_created += 1

    # Draft messages (3 messages)
    draft_messages = [
        {
            "to": CONTACTS[4],
            "subject": "Marketing Campaign Proposal",
            "body_text": """Hi Eve,

I've been thinking about a new campaign idea:

[Draft notes]
- Target: Enterprise customers
- Theme: Security and compliance
- Channels: LinkedIn, email nurture
- Budget: TBD

Need to add:
- Timeline
- Success metrics
- Creative brief""",
        },
        {
            "to": CONTACTS[7],
            "subject": "Re: Sales Forecast Q1 2026",
            "body_text": """Henry,

Thanks for the forecast. A few questions:

1. What's driving the March spike?
2. Are these numbers including the Acme deal?
3.

[Need to finish this]""",
        },
        {
            "to": CONTACTS[12],
            "subject": "Infrastructure Concerns",
            "body_text": """Maya,

I wanted to discuss some concerns about our current infrastructure setup.

Points to cover:
- Database replication lag
- CDN cache invalidation issues
-

[WIP - will finish tomorrow]""",
        },
    ]

    if drafts_id:
        for msg_data in draft_messages:
            storage.create_message({
                "folder_id": drafts_id,
                "from_address": ME["email"],
                "to_addresses": [msg_data["to"]["email"]],
                "subject": msg_data["subject"],
                "body_text": msg_data["body_text"],
                "is_read": True,
                "status": MessageStatus.DRAFT.value,
                "received_at": base_time.isoformat(),
                "headers": {"To": f"{msg_data['to']['name']} <{msg_data['to']['email']}>"},
            })
            messages_created += 1

    # Trash messages (4 messages - deleted emails)
    trash_messages = [
        {
            "from": CONTACTS[random.randint(0, len(CONTACTS)-1)],
            "subject": "Old Meeting Notes - Can Delete",
            "body_text": """Team,

Here are the notes from last month's retrospective. We've already actioned all items.

Feel free to delete this after review.

Thanks""",
            "hours_ago": 120,
            "is_read": True,
        },
        {
            "from": CONTACTS[random.randint(0, len(CONTACTS)-1)],
            "subject": "RE: Outdated Info",
            "body_text": """This information is no longer relevant. The project was cancelled.

Archiving for reference.""",
            "hours_ago": 200,
            "is_read": True,
        },
        {
            "from": CONTACTS[random.randint(0, len(CONTACTS)-1)],
            "subject": "Test Email - Please Ignore",
            "body_text": """This is a test email to verify the system is working.

Please delete.""",
            "hours_ago": 96,
            "is_read": True,
        },
        {
            "from": CONTACTS[random.randint(0, len(CONTACTS)-1)],
            "subject": "Duplicate: Q4 Report",
            "body_text": """Accidentally sent this twice. Please use the other copy.

Apologies for the confusion.""",
            "hours_ago": 150,
            "is_read": True,
        },
    ]

    if trash_id:
        for msg_data in trash_messages:
            storage.create_message({
                "folder_id": trash_id,
                "from_address": msg_data["from"]["email"],
                "to_addresses": [ME["email"]],
                "subject": msg_data["subject"],
                "body_text": msg_data["body_text"],
                "is_read": msg_data.get("is_read", True),
                "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
                "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
            })
            messages_created += 1

    # Spam messages (5 messages - junk mail)
    spam_messages = [
        {
            "from": {"name": "Nigerian Prince", "email": "prince@totallylegit.ng"},
            "subject": "URGENT: $10 Million Inheritance Awaits!!!",
            "body_text": """Dear Beloved Friend,

I am Prince Abdullah from Nigeria. My late father left $10 MILLION dollars and I need YOUR help to transfer it!!!

Please send your bank details immediately!!!

God Bless,
Prince Abdullah""",
            "hours_ago": 24,
            "is_read": False,
        },
        {
            "from": {"name": "Pharmacy Online", "email": "deals@ch3ap-m3ds.xyz"},
            "subject": "85% OFF All Medications - LIMITED TIME!!!",
            "body_text": """BUY NOW!!! CHEAP MEDICATIONS!!!

All prescriptions 85% off!!!
No doctor needed!!!
Ship worldwide!!!

Click here: [SUSPICIOUS LINK REMOVED]""",
            "hours_ago": 36,
            "is_read": False,
        },
        {
            "from": {"name": "Lottery Winner", "email": "winner@lotto-prize.ru"},
            "subject": "YOU WON $5,000,000!!!",
            "body_text": """CONGRATULATIONS!!!

Your email was randomly selected to WIN $5,000,000!!!

To claim your prize, send $500 processing fee to:
[SUSPICIOUS PAYMENT DETAILS REMOVED]

ACT NOW!!!""",
            "hours_ago": 48,
            "is_read": False,
        },
        {
            "from": {"name": "Tech Support", "email": "support@micr0s0ft-help.com"},
            "subject": "ALERT: Your computer has a virus!!!",
            "body_text": """URGENT SECURITY ALERT!!!

Our system detected 47 VIRUSES on your computer!!!

Call 1-800-SCAM-NOW immediately for free virus removal!!!

Your Microsoft Support Team""",
            "hours_ago": 72,
            "is_read": False,
        },
        {
            "from": {"name": "Hot Singles", "email": "dating@meet-now.biz"},
            "subject": "3 Hot Singles in Your Area Want to Meet!!!",
            "body_text": """Don't be alone tonight!!!

Beautiful singles are waiting to meet YOU!!!

Click here to see profiles: [SUSPICIOUS LINK REMOVED]

Unsubscribe: [MORE SUSPICIOUS LINKS]""",
            "hours_ago": 60,
            "is_read": False,
        },
    ]

    if spam_id:
        for msg_data in spam_messages:
            storage.create_message({
                "folder_id": spam_id,
                "from_address": msg_data["from"]["email"],
                "to_addresses": [ME["email"]],
                "subject": msg_data["subject"],
                "body_text": msg_data["body_text"],
                "is_read": msg_data.get("is_read", False),
                "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
                "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
            })
            messages_created += 1

    # Archive messages (6 messages - old but kept for reference)
    archive_messages = [
        {
            "from": CONTACTS[0],
            "subject": "Project Alpha - Final Report",
            "body_text": """Team,

Attached is the final report for Project Alpha. The project was completed successfully on time and under budget.

Key achievements:
- 30% performance improvement
- Zero critical bugs at launch
- 95% user satisfaction score

Great work everyone!

Alice""",
            "hours_ago": 720,  # 30 days ago
            "is_read": True,
            "attachments": [{"filename": "Project_Alpha_Final_Report.pdf", "size": 2500000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[3],
            "subject": "2025 Annual Financial Summary",
            "body_text": """Hi,

Please find attached the 2025 annual financial summary for your records.

Highlights:
- Revenue: $4.2M (+25% YoY)
- Expenses: $3.1M
- Net Income: $1.1M

Detailed breakdown in the attachment.

David - Finance""",
            "hours_ago": 600,  # 25 days ago
            "is_read": True,
            "attachments": [{"filename": "2025_Financial_Summary.xlsx", "size": 890000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}],
        },
        {
            "from": CONTACTS[6],
            "subject": "Employee Handbook - Updated Version",
            "body_text": """Dear Team,

The employee handbook has been updated for 2026. Key changes:

- Remote work policy updates
- New benefits package details
- Updated code of conduct

Please review and acknowledge.

Grace - HR""",
            "hours_ago": 480,  # 20 days ago
            "is_read": True,
            "attachments": [{"filename": "Employee_Handbook_2026.pdf", "size": 3400000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[10],
            "subject": "Contract Signed: Enterprise Agreement",
            "body_text": """Good news! The enterprise agreement with TechGiant Inc has been fully executed.

Contract Details:
- Term: 3 years
- Value: $500K/year
- Start Date: January 1, 2026

Signed copies attached for your records.

Karen - Legal""",
            "hours_ago": 360,  # 15 days ago
            "is_read": True,
            "attachments": [{"filename": "TechGiant_Enterprise_Agreement_Signed.pdf", "size": 450000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[12],
            "subject": "Infrastructure Upgrade Complete",
            "body_text": """Team,

The infrastructure upgrade is complete. Summary:

- Database migrated to new cluster
- CDN upgraded to enterprise tier
- Monitoring systems enhanced
- All security patches applied

Performance metrics show 40% improvement in response times.

Maya - Operations""",
            "hours_ago": 240,  # 10 days ago
            "is_read": True,
        },
        {
            "from": CONTACTS[11],
            "subject": "Product Roadmap 2026 - Final Version",
            "body_text": """Hi all,

The 2026 product roadmap has been finalized and approved by leadership.

Q1 Focus:
- Mobile app launch
- Dark mode
- Performance improvements

Q2 Focus:
- Calendar integration
- Advanced filters
- API v3

Detailed roadmap attached.

Leo - Product""",
            "hours_ago": 168,  # 7 days ago
            "is_read": True,
            "is_starred": True,
            "attachments": [{"filename": "Product_Roadmap_2026.pdf", "size": 1200000, "content_type": "application/pdf"}],
        },
    ]

    if archive_id:
        for msg_data in archive_messages:
            storage.create_message({
                "folder_id": archive_id,
                "from_address": msg_data["from"]["email"],
                "to_addresses": [ME["email"]],
                "subject": msg_data["subject"],
                "body_text": msg_data["body_text"],
                "is_read": msg_data.get("is_read", True),
                "is_starred": msg_data.get("is_starred", False),
                "attachments": msg_data.get("attachments", []),
                "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
                "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
            })
            messages_created += 1

    # Update folder counts
    storage._update_folder_counts()

    return messages_created


if __name__ == "__main__":
    count = generate_sample_messages(force_regenerate=True)
    print(f"Generated {count} sample messages")
