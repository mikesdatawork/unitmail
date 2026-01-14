"""
Sample Data Generator for unitMail.

This module generates realistic sample email messages for testing
and development purposes. Creates 50+ messages with threads,
attachments, and various states.
"""

import random
from datetime import datetime, timedelta
from uuid import uuid4

from .local_storage import get_local_storage, MessagePriority, MessageStatus


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
    storage = get_local_storage()

    if not force_regenerate and storage.get_message_count() > 0:
        return storage.get_message_count()

    if force_regenerate:
        storage.clear_all_messages()

    folders = storage.get_folders()
    inbox_id = next((f["id"] for f in folders if f["name"] == "Inbox"), None)
    sent_id = next((f["id"] for f in folders if f["name"] == "Sent"), None)
    drafts_id = next((f["id"] for f in folders if f["name"] == "Drafts"), None)

    messages_created = 0
    base_time = datetime.utcnow()

    # Thread 1: Project Planning (5 messages)
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

    for i, msg_data in enumerate(thread1_messages):
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

    # Thread 2: Bug Report (4 messages)
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
            "priority": MessagePriority.URGENT,
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
            "priority": msg_data.get("priority", MessagePriority.NORMAL),
            "attachments": msg_data.get("attachments", []),
            "thread_id": thread2_id,
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
        })
        messages_created += 1

    # Thread 3: Weekly Newsletter Discussion (3 messages)
    thread3_id = str(uuid4())
    thread3_messages = [
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
        {
            "from": CONTACTS[11],
            "subject": "Re: Newsletter Content Ideas for February",
            "body_text": """Great ideas Eve!

I can contribute:
- A deep dive into our new analytics dashboard
- User feedback highlights from January

Also, we just crossed 10,000 active users - that would make a great announcement!

Leo""",
            "hours_ago": 70,
            "is_read": True,
        },
        {
            "from": CONTACTS[4],
            "subject": "Re: Newsletter Content Ideas for February",
            "body_text": """Perfect Leo! The 10K milestone is definitely newsworthy.

I'll draft the announcement. Can you send me the exact numbers and any relevant metrics?

Eve""",
            "hours_ago": 68,
            "is_read": True,
            "is_starred": True,
            "attachments": [{"filename": "newsletter_draft.docx", "size": 67000, "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}],
        },
    ]

    for msg_data in thread3_messages:
        storage.create_message({
            "folder_id": inbox_id,
            "from_address": msg_data["from"]["email"],
            "to_addresses": [ME["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": msg_data.get("is_read", False),
            "is_starred": msg_data.get("is_starred", False),
            "attachments": msg_data.get("attachments", []),
            "thread_id": thread3_id,
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"From": f"{msg_data['from']['name']} <{msg_data['from']['email']}>"},
        })
        messages_created += 1

    # Individual messages (remaining to reach 50+)
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
            "priority": MessagePriority.HIGH,
            "attachments": [
                {"filename": "budget_proposal_q1.xlsx", "size": 125000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                {"filename": "infrastructure_plan.pdf", "size": 890000, "content_type": "application/pdf"},
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
                {"filename": "ml_email_classification.pdf", "size": 2450000, "content_type": "application/pdf"},
                {"filename": "summary_notes.md", "size": 8500, "content_type": "text/markdown"},
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
            "priority": MessagePriority.HIGH,
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

📈 Active Users: +12% MoM
⏱️ Avg Session Duration: 8.5 minutes (+2.1 min)
🔄 Feature Adoption: Dashboard widgets at 78%
📱 Mobile Usage: 34% of total traffic

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
                {"filename": "Brand_Guidelines_v3.pdf", "size": 5400000, "content_type": "application/pdf"},
                {"filename": "Logo_Pack.zip", "size": 12500000, "content_type": "application/zip"},
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
            "from": CONTACTS[2],
            "subject": "Design Feedback Needed",
            "body_text": """Hi!

I've created three design options for the new onboarding flow. Could you provide feedback?

Option A: Minimal wizard (3 steps)
Option B: Interactive tutorial (5 steps)
Option C: Video walkthrough + quick setup

Figma link attached. I'd like to finalize by end of week.

Carol""",
            "hours_ago": 34,
            "is_read": True,
            "attachments": [{"filename": "Onboarding_Designs.fig", "size": 3400000, "content_type": "application/octet-stream"}],
        },
        {
            "from": CONTACTS[3],
            "subject": "Invoice #2026-0042",
            "body_text": """Please find attached invoice for January consulting services.

Invoice Details:
- Invoice #: 2026-0042
- Amount: $4,500.00
- Due Date: February 15, 2026
- Payment Terms: Net 30

Wire transfer details included in the PDF.

David - Finance""",
            "hours_ago": 38,
            "is_read": True,
            "attachments": [{"filename": "Invoice_2026-0042.pdf", "size": 125000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[4],
            "subject": "Social Media Campaign Results",
            "body_text": """Team,

The holiday campaign exceeded expectations!

Results:
- Impressions: 2.4M (+180%)
- Engagement Rate: 4.2%
- Click-through Rate: 2.8%
- Conversions: 1,247
- ROI: 340%

Top performing content was the product demo video. Planning to create more similar content.

Eve - Marketing""",
            "hours_ago": 42,
            "is_read": True,
            "is_starred": True,
            "attachments": [
                {"filename": "campaign_metrics.xlsx", "size": 145000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                {"filename": "top_posts.png", "size": 1200000, "content_type": "image/png"},
            ],
        },
        {
            "from": CONTACTS[5],
            "subject": "Database Migration Plan",
            "body_text": """Hi all,

Here's the detailed plan for the database migration:

Phase 1: Schema updates (Week 1)
Phase 2: Data migration (Week 2)
Phase 3: Application updates (Week 3)
Phase 4: Testing & validation (Week 4)

Risk assessment and rollback procedures attached.

Frank - Engineering""",
            "hours_ago": 50,
            "is_read": True,
            "attachments": [
                {"filename": "Migration_Plan.pdf", "size": 450000, "content_type": "application/pdf"},
                {"filename": "Rollback_Procedures.md", "size": 12000, "content_type": "text/markdown"},
            ],
        },
        {
            "from": CONTACTS[6],
            "subject": "New Hire Onboarding - Week of Jan 20",
            "body_text": """Team leads,

We have 3 new hires starting next week:

1. Sarah (Engineering) - Reports to Frank
2. Mike (Marketing) - Reports to Eve
3. Lisa (Support) - Reports to Jack

Please ensure:
- Workstations are ready
- Access credentials are set up
- First week schedule is prepared
- Buddy assignments confirmed

Let me know if you need anything.

Grace - HR""",
            "hours_ago": 54,
            "is_read": True,
        },
        {
            "from": CONTACTS[7],
            "subject": "Customer Meeting Notes - Acme Corp",
            "body_text": """Quick summary from today's Acme Corp meeting:

Attendees: John (CEO), Maria (CTO), Us

Key Points:
- Very interested in enterprise features
- Concerns about data residency (need EU option)
- Budget approved for 500 seats
- Want to start pilot in February

Action items:
1. Send enterprise proposal
2. Clarify EU data center timeline
3. Schedule technical deep dive

Henry""",
            "hours_ago": 58,
            "is_read": False,
            "attachments": [{"filename": "meeting_notes.txt", "size": 12000, "content_type": "text/plain"}],
        },
        {
            "from": CONTACTS[8],
            "subject": "Conference Presentation Materials",
            "body_text": """Hi,

Attached are the slides for next month's tech conference presentation.

Talk: "Building Secure Email Systems at Scale"
Duration: 45 minutes + Q&A

Could you review slides 15-20? Those cover the architecture section and I want to make sure it's accurate.

Iris""",
            "hours_ago": 62,
            "is_read": False,
            "attachments": [{"filename": "Conference_Slides.pptx", "size": 8900000, "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}],
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
            "priority": MessagePriority.URGENT,
        },
        {
            "from": CONTACTS[10],
            "subject": "Contract Renewal - CloudHost Services",
            "body_text": """The CloudHost services contract is up for renewal on Feb 28.

Current terms:
- 3-year contract
- $8,500/month
- 99.9% SLA

They're offering:
- 2-year renewal
- $7,800/month (8% reduction)
- 99.95% SLA upgrade

Recommendation: Accept the renewal. Let me know if you need negotiation support.

Karen - Legal""",
            "hours_ago": 66,
            "is_read": True,
            "attachments": [{"filename": "CloudHost_Renewal_Terms.pdf", "size": 234000, "content_type": "application/pdf"}],
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
            "from": CONTACTS[12],
            "subject": "Incident Report - Jan 10 Outage",
            "body_text": """Post-mortem report for the January 10th outage.

Duration: 47 minutes
Impact: 12% of users affected
Root Cause: Database connection pool exhaustion

Timeline and remediation steps in attached document.

Action items for prevention:
1. Implement connection pool monitoring
2. Add auto-scaling for DB connections
3. Update alerting thresholds

Maya - Operations""",
            "hours_ago": 74,
            "is_read": True,
            "attachments": [{"filename": "Incident_Report_20260110.pdf", "size": 156000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[13],
            "subject": "A/B Test Results - Checkout Flow",
            "body_text": """A/B test completed for the new checkout flow.

Results:
- Variant A (current): 3.2% conversion
- Variant B (simplified): 4.1% conversion

Statistical significance: 99%
Lift: +28%

Recommendation: Ship Variant B to all users.

Full analysis attached.

Nathan - Analytics""",
            "hours_ago": 78,
            "is_read": True,
            "attachments": [{"filename": "AB_Test_Checkout.xlsx", "size": 89000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}],
        },
        {
            "from": CONTACTS[14],
            "subject": "Photography Assets for Blog",
            "body_text": """Hi!

I've uploaded new photography assets for the blog:

- Team photos (updated headshots)
- Office space images
- Product screenshots
- Stock photo collection

All images are in the shared drive under /Marketing/Photos/2026/

Let me know if you need specific shots.

Olivia - Creative""",
            "hours_ago": 82,
            "is_read": True,
            "attachments": [
                {"filename": "team_headshots.jpg", "size": 3400000, "content_type": "image/jpeg"},
                {"filename": "office_tour.jpg", "size": 2800000, "content_type": "image/jpeg"},
                {"filename": "product_screenshot_1.png", "size": 890000, "content_type": "image/png"},
            ],
        },
        {
            "from": CONTACTS[0],
            "subject": "Reminder: 1:1 Meeting Tomorrow",
            "body_text": """Just a reminder about our 1:1 tomorrow at 3pm.

Agenda:
- Q1 goals review
- Upcoming projects
- Any concerns or blockers

Let me know if you need to reschedule.

Alice""",
            "hours_ago": 20,
            "is_read": True,
            "attachments": [{"filename": "agenda.txt", "size": 3400, "content_type": "text/plain"}],
        },
        {
            "from": CONTACTS[1],
            "subject": "Quick Question About API Rate Limits",
            "body_text": """Hey,

Quick question - what's the current rate limit for the public API?

A customer is asking about bulk operations and I want to give them accurate info.

Thanks!
Bob""",
            "hours_ago": 3,
            "is_read": False,
        },
        {
            "from": CONTACTS[2],
            "subject": "Accessibility Audit Complete",
            "body_text": """Good news! The accessibility audit is complete.

Score: 94/100 (WCAG 2.1 AA compliant)

Minor issues found:
- 3 missing alt texts
- 2 color contrast warnings
- 1 keyboard navigation issue

Full report attached. These should be quick fixes.

Carol""",
            "hours_ago": 36,
            "is_read": True,
            "attachments": [{"filename": "Accessibility_Audit.pdf", "size": 567000, "content_type": "application/pdf"}],
        },
        {
            "from": CONTACTS[3],
            "subject": "Expense Report Reminder",
            "body_text": """Friendly reminder that expense reports for January are due by Feb 5th.

Please submit via the expense portal:
1. Log into expenses.company.com
2. Upload receipts
3. Categorize expenses
4. Submit for approval

Questions? Reply to this email.

David - Finance""",
            "hours_ago": 90,
            "is_read": True,
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
            "from": CONTACTS[8],
            "subject": "Paper Submission Deadline Extended",
            "body_text": """Good news! The conference has extended their submission deadline by one week.

New deadline: February 15, 2026

This gives us more time to refine our methodology section. I'll send updated drafts by Friday.

Iris""",
            "hours_ago": 5,
            "is_read": False,
        },
        {
            "from": CONTACTS[12],
            "subject": "Infrastructure Cost Report",
            "body_text": """Monthly infrastructure cost breakdown:

Cloud Services: $12,450 (-8% from last month)
CDN: $2,100
Monitoring: $890
Backups: $450

Total: $15,890

Good news - our optimization efforts are paying off. Full breakdown attached.

Maya - Operations""",
            "hours_ago": 28,
            "is_read": True,
            "attachments": [{"filename": "Infra_Costs_Jan2026.xlsx", "size": 45000, "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}],
        },
        {
            "from": CONTACTS[14],
            "subject": "Video Content Review Request",
            "body_text": """Hi!

I've finished the product explainer video draft. Before we share with stakeholders, could you review:

- Technical accuracy of the features shown
- Any messaging that needs adjustment
- Call-to-action effectiveness

Video link: drive.company.com/videos/explainer-v1

Thanks!
Olivia - Creative""",
            "hours_ago": 16,
            "is_read": False,
            "is_starred": True,
            "attachments": [
                {"filename": "video_script.docx", "size": 34000, "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                {"filename": "storyboard.pdf", "size": 2300000, "content_type": "application/pdf"},
            ],
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
            "priority": msg_data.get("priority", MessagePriority.NORMAL),
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

    for msg_data in sent_messages:
        storage.create_message({
            "folder_id": sent_id,
            "from_address": ME["email"],
            "to_addresses": [msg_data["to"]["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": True,
            "status": MessageStatus.SENT,
            "sent_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "received_at": (base_time - timedelta(hours=msg_data["hours_ago"])).isoformat(),
            "headers": {"To": f"{msg_data['to']['name']} <{msg_data['to']['email']}>"},
        })
        messages_created += 1

    # Draft messages (2 messages)
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
    ]

    for msg_data in draft_messages:
        storage.create_message({
            "folder_id": drafts_id,
            "from_address": ME["email"],
            "to_addresses": [msg_data["to"]["email"]],
            "subject": msg_data["subject"],
            "body_text": msg_data["body_text"],
            "is_read": True,
            "status": MessageStatus.DRAFT,
            "received_at": base_time.isoformat(),
            "headers": {"To": f"{msg_data['to']['name']} <{msg_data['to']['email']}>"},
        })
        messages_created += 1

    return messages_created


if __name__ == "__main__":
    count = generate_sample_messages(force_regenerate=True)
    print(f"Generated {count} sample messages")
