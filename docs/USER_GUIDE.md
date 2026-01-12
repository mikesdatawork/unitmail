# unitMail User Guide

Welcome to unitMail, your independent email client. This guide covers everyday use of unitMail for reading, composing, and managing your email.

## Table of Contents

- [Getting Started](#getting-started)
- [Composing and Sending Email](#composing-and-sending-email)
- [Reading and Organizing Email](#reading-and-organizing-email)
- [Contact Management](#contact-management)
- [Search Functionality](#search-functionality)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Settings Overview](#settings-overview)

---

## Getting Started

### Launching unitMail

Start unitMail from your application menu or run from terminal:

```bash
unitmail
```

### The Main Interface

The unitMail interface uses a three-pane layout:

```
+------------------+------------------------+------------------------+
|                  |                        |                        |
|   Folder List    |    Message List        |    Message Preview     |
|                  |                        |                        |
|   - Inbox        |  From | Subject | Date |                        |
|   - Sent         |  -----------------------                        |
|   - Drafts       |  sender@example.com    |  Full message content  |
|   - Trash        |  Meeting tomorrow      |  displayed here with   |
|   - Custom...    |  Jan 10, 2026          |  attachments           |
|                  |                        |                        |
+------------------+------------------------+------------------------+
|                       Status Bar: Queue | Connection              |
+-----------------------------------------------------------------------+
```

#### Folder Panel (Left)

- **Inbox**: Received messages
- **Sent**: Messages you've sent
- **Drafts**: Unsent message drafts
- **Trash**: Deleted messages (auto-emptied after 30 days)
- **Custom Folders**: Your personal organization

#### Message List (Center)

Shows messages in the selected folder with:
- Sender/recipient name and address
- Subject line
- Date and time received/sent
- Status icons (unread, starred, attachments)

#### Preview Pane (Right)

Displays the full content of the selected message including:
- Header information (From, To, CC, Subject, Date)
- Message body (plain text or rendered HTML)
- Attachment list with download options

### First Steps

1. **Check your inbox**: Click "Inbox" in the folder list
2. **Read a message**: Click any message to see it in the preview pane
3. **Compose new email**: Click the "Compose" button or press `C`
4. **Reply to a message**: Select a message and press `R`

---

## Composing and Sending Email

### Creating a New Message

1. Click **Compose** in the toolbar, or press `C`
2. The compose window opens:

```
+-----------------------------------------------------------+
| To:     [recipient@example.com                        ] X |
| CC:     [                                             ]   |
| BCC:    [                                             ]   |
| Subject:[Your subject line                            ]   |
+-----------------------------------------------------------+
|                                                           |
|  Message body area                                        |
|                                                           |
|  Type your message here...                                |
|                                                           |
+-----------------------------------------------------------+
| [Attach] [Encrypt] [Sign]         [Save Draft] [Send]     |
+-----------------------------------------------------------+
```

### Adding Recipients

- **To**: Primary recipients (required)
- **CC**: Carbon copy recipients (visible to all)
- **BCC**: Blind carbon copy (hidden from other recipients)

Type an email address and press `Tab` or `Enter` to add it. You can add multiple recipients.

**Auto-complete**: As you type, unitMail suggests contacts from your address book.

### Writing Your Message

#### Plain Text Mode

The default mode for simple, universal compatibility:

```
Hello,

This is a plain text message.

Best regards,
Your Name
```

#### Rich Text Mode

Click **Format** or press `Ctrl+Shift+F` to enable rich text:

- **Bold**: `Ctrl+B`
- **Italic**: `Ctrl+I`
- **Underline**: `Ctrl+U`
- **Bullet List**: Click the list icon
- **Numbered List**: Click the numbered list icon

### Attaching Files

1. Click **Attach** or press `Ctrl+Shift+A`
2. Select files from the file browser
3. Attached files appear below the message body:

```
Attachments:
[x] document.pdf (2.1 MB)
[x] image.png (540 KB)
    Total: 2.6 MB / 25 MB limit
```

**Limits**:
- Maximum file size: 25 MB per file
- Maximum total size: 35 MB per message
- Some file types may be blocked (e.g., .exe)

### Encrypting Messages

If you have the recipient's PGP public key:

1. Click **Encrypt** to toggle encryption
2. The lock icon indicates encryption status
3. unitMail automatically encrypts if the recipient's key is available

To sign your message (proves it came from you):
1. Click **Sign** to toggle digital signature
2. Your private key passphrase may be required

### Sending

1. Click **Send** or press `Ctrl+Enter`
2. The message enters the outbound queue
3. Status appears in the status bar: "Sending..." then "Sent"

If sending fails, the message moves to your **Outbox** for retry.

### Saving Drafts

- Click **Save Draft** or press `Ctrl+S`
- Drafts are saved to the **Drafts** folder
- Auto-save runs every 60 seconds while composing
- Resume drafts by opening from the Drafts folder

---

## Reading and Organizing Email

### Reading Messages

1. Select a folder (e.g., Inbox)
2. Click a message to view in the preview pane
3. Double-click to open in a full window

#### Message Header

```
From:    John Doe <john@example.com>
To:      you@yourdomain.com
Date:    January 10, 2026 at 2:30 PM
Subject: Meeting Tomorrow

[Reply] [Reply All] [Forward] [Delete] [Star] [More...]
```

#### Viewing Attachments

Attachments appear at the bottom of the message:

```
Attachments (2):
[Download] presentation.pdf (4.2 MB)
[Download] notes.docx (150 KB)

[Download All]
```

Click **Download** to save to your computer.

### Replying to Messages

- **Reply** (`R`): Reply to sender only
- **Reply All** (`Shift+R`): Reply to sender and all recipients
- **Forward** (`F`): Send message to someone else

When replying, the original message is quoted:

```
On January 10, 2026, John Doe wrote:
> Original message content here
> Second line of original

Your reply here...
```

### Organizing with Folders

#### Creating Folders

1. Right-click in the folder list
2. Select **New Folder**
3. Enter folder name
4. Optionally choose a parent folder for nesting

#### Moving Messages

**Method 1: Drag and Drop**
- Click and drag a message to a folder

**Method 2: Right-Click Menu**
1. Right-click the message
2. Select **Move to** > choose folder

**Method 3: Keyboard**
1. Select message(s)
2. Press `V` to open folder picker
3. Type to filter, press `Enter` to move

#### Deleting Messages

1. Select message(s)
2. Press `Delete` or click the trash icon
3. Messages move to **Trash**

To permanently delete:
1. Open **Trash** folder
2. Select messages or click **Empty Trash**
3. Confirm permanent deletion

### Message Flags

| Icon | Meaning | Shortcut |
|------|---------|----------|
| Unread dot | Unread message | `U` to toggle |
| Star | Starred/important | `S` to toggle |
| Flag | Flagged for follow-up | `!` to toggle |
| Paperclip | Has attachments | - |
| Lock | Encrypted | - |

### Filtering Messages

Click the filter dropdown above the message list:

- **All Mail**: Show all messages
- **Unread**: Show only unread messages
- **Starred**: Show starred messages
- **Has Attachments**: Show messages with attachments
- **Encrypted**: Show encrypted messages

---

## Contact Management

### Viewing Contacts

1. Click **Contacts** in the main menu or press `Ctrl+Shift+C`
2. The contacts window shows your address book:

```
+-------------------+--------------------------------+
| Search: [       ] |  Name: John Doe                |
+-------------------+  Email: john@example.com       |
| A                 |  Phone: +1 555-123-4567        |
|   Alice Smith     |  Notes: Met at conference 2025 |
|   Andy Johnson    |                                |
| B                 |  PGP Key: Imported             |
|   Bob Williams    |                                |
| J                 |  [Edit] [Delete] [Send Email]  |
|   John Doe  <--   |                                |
+-------------------+--------------------------------+
```

### Adding Contacts

#### Method 1: Manual Entry

1. Click **New Contact** or press `N`
2. Fill in the fields:
   - Name (required)
   - Email (required)
   - Phone (optional)
   - Notes (optional)
   - PGP Public Key (optional)
3. Click **Save**

#### Method 2: From Received Email

1. Open a message
2. Click the sender's name or email
3. Select **Add to Contacts**
4. Edit details if needed
5. Click **Save**

### Editing Contacts

1. Select a contact
2. Click **Edit** or press `E`
3. Modify fields
4. Click **Save**

### Importing/Exporting Contacts

**Import**:
1. Click **File** > **Import Contacts**
2. Select file format (vCard, CSV)
3. Choose the file
4. Review and confirm

**Export**:
1. Click **File** > **Export Contacts**
2. Choose format (vCard, CSV)
3. Select location
4. Click **Save**

### Contact Groups

Create groups for easier sending:

1. Click **New Group**
2. Name the group (e.g., "Work Team")
3. Add contacts to the group
4. When composing, type the group name in To/CC/BCC

---

## Search Functionality

### Basic Search

1. Click the search box or press `/`
2. Type your search terms
3. Results appear as you type

```
Search: [meeting budget              ]  [Search]

Results in: All Folders  v    Sort by: Relevance  v

3 results found:
+--------------------------------------------+
| From: CFO@company.com                      |
| Subject: Q4 Budget Meeting                 |
| Date: Dec 15, 2025                         |
+--------------------------------------------+
| From: team@company.com                     |
| Subject: Meeting notes - budget review     |
| Date: Dec 10, 2025                         |
+--------------------------------------------+
```

### Advanced Search

Click **Advanced** or press `Ctrl+Shift+F` for detailed search:

| Field | Description | Example |
|-------|-------------|---------|
| From | Sender email or name | `from:john@example.com` |
| To | Recipient | `to:me@domain.com` |
| Subject | Subject line | `subject:invoice` |
| Body | Message content | `body:quarterly report` |
| Date | Date range | `date:2025-12-01..2025-12-31` |
| Has | Attachment/encryption | `has:attachment` |
| Is | Message status | `is:unread is:starred` |
| Folder | Specific folder | `folder:inbox` |

### Search Operators

Combine terms with operators:

| Operator | Function | Example |
|----------|----------|---------|
| AND | Both terms required | `budget AND meeting` |
| OR | Either term | `budget OR forecast` |
| NOT | Exclude term | `meeting NOT cancelled` |
| "" | Exact phrase | `"quarterly budget"` |
| * | Wildcard | `report*` matches report, reports, reporting |

### Saving Searches

1. Perform a search
2. Click **Save Search** or press `Ctrl+S`
3. Name your saved search
4. Access later from **Saved Searches** in the folder list

---

## Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action |
|----------|--------|
| `C` | Compose new message |
| `/` | Focus search box |
| `?` | Show keyboard shortcuts |
| `Ctrl+Q` | Quit application |
| `Ctrl+,` | Open settings |
| `F1` | Open help |
| `Ctrl+Shift+C` | Open contacts |

### Message List

| Shortcut | Action |
|----------|--------|
| `J` / `Down` | Next message |
| `K` / `Up` | Previous message |
| `Enter` | Open selected message |
| `Space` | Scroll / select next unread |
| `U` | Toggle read/unread |
| `S` | Toggle star |
| `!` | Toggle flag |
| `V` | Move to folder |
| `Delete` | Move to trash |
| `Shift+Delete` | Delete permanently |

### Reading Messages

| Shortcut | Action |
|----------|--------|
| `R` | Reply |
| `Shift+R` | Reply all |
| `F` | Forward |
| `A` | Archive |
| `Ctrl+P` | Print message |
| `Ctrl+U` | View source/headers |

### Composing

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Send message |
| `Ctrl+S` | Save draft |
| `Ctrl+Shift+A` | Attach file |
| `Escape` | Close compose (saves draft) |
| `Ctrl+B` | Bold (rich text) |
| `Ctrl+I` | Italic (rich text) |
| `Ctrl+U` | Underline (rich text) |

### Navigation

| Shortcut | Action |
|----------|--------|
| `G` then `I` | Go to Inbox |
| `G` then `S` | Go to Sent |
| `G` then `D` | Go to Drafts |
| `G` then `T` | Go to Trash |
| `Ctrl+1-9` | Go to folder 1-9 |

---

## Settings Overview

Open settings with **Edit** > **Preferences** or press `Ctrl+,`

### Account Settings

```
Account Settings
+------------------------------------------+
| Display Name:  [Your Name              ] |
| Email Address: you@yourdomain.com        |
|                                          |
| [Change Password]                        |
| [Configure 2FA]                          |
+------------------------------------------+
```

- **Display Name**: Name shown on outgoing emails
- **Email Address**: Your configured email (read-only)
- **Change Password**: Update your account password
- **Configure 2FA**: Enable two-factor authentication

### Server Settings

```
Server Settings
+------------------------------------------+
| Gateway: [gateway.unitmail.org        ]  |
| Port:    [443                         ]  |
|                                          |
| [x] Use TLS                              |
| [x] Verify certificates                  |
|                                          |
| Connection Status: Connected             |
| [Test Connection]                        |
+------------------------------------------+
```

Configure your gateway connection for sending/receiving.

### Appearance

```
Appearance
+------------------------------------------+
| Theme:       [System Default  v]         |
|                                          |
| Font Size:   [Medium          v]         |
|                                          |
| [x] Show preview pane                    |
| [x] Show folder counts                   |
| [ ] Compact message list                 |
|                                          |
| Preview Lines: [3             v]         |
+------------------------------------------+
```

- **Theme**: Light, Dark, or System Default
- **Font Size**: Small, Medium, Large, Extra Large
- **Layout Options**: Customize the interface

### Composing

```
Composing
+------------------------------------------+
| Default Format: [Plain Text   v]         |
|                                          |
| Signature:                               |
| +--------------------------------------+ |
| | Best regards,                        | |
| | Your Name                            | |
| | your@email.com                       | |
| +--------------------------------------+ |
|                                          |
| [x] Auto-save drafts every 60 seconds    |
| [x] Spell check while typing             |
| [x] Quote original message in reply      |
+------------------------------------------+
```

### Security

```
Security
+------------------------------------------+
| PGP/GPG Configuration                    |
| Key ID: 0xABCD1234EFGH5678               |
| [Generate New Key] [Import Key]          |
|                                          |
| [x] Sign outgoing messages by default    |
| [x] Auto-encrypt if recipient key known  |
| [x] Warn before sending unencrypted      |
|                                          |
| Database Encryption                      |
| Status: Encrypted                        |
| [Change Passphrase]                      |
+------------------------------------------+
```

### Notifications

```
Notifications
+------------------------------------------+
| [x] Desktop notifications for new mail   |
| [x] Play sound on new mail               |
| Sound: [Default System Sound  v]         |
|                                          |
| [x] Show in system tray                  |
| [x] Show unread count badge              |
|                                          |
| Notification Preview:                    |
| [x] Show sender                          |
| [x] Show subject                         |
| [ ] Show message preview                 |
+------------------------------------------+
```

### Quota and Usage

```
Quota & Usage
+------------------------------------------+
| Daily Sending Quota                      |
| Used: 15 / 100 messages                  |
| [========--------------------------]     |
| Resets: Tomorrow at 00:00 UTC            |
|                                          |
| Storage Usage                            |
| Local: 2.3 GB used                       |
| Messages: 12,453                         |
| Attachments: 1.8 GB                      |
|                                          |
| [Manage Storage] [Export Data]           |
+------------------------------------------+
```

### Backup

```
Backup Settings
+------------------------------------------+
| Automatic Backup                         |
| [x] Enable automatic backups             |
| Frequency: [Daily           v]           |
| Time: [02:00               v]            |
|                                          |
| Backup Location:                         |
| [/home/user/backups/unitmail          ]  |
| [Browse]                                 |
|                                          |
| Retention: Keep [30] days of backups     |
|                                          |
| [Backup Now] [Restore from Backup]       |
|                                          |
| Last Backup: Today at 02:00              |
+------------------------------------------+
```

---

## Tips and Best Practices

### Email Etiquette

1. **Clear subject lines**: Make subjects descriptive and specific
2. **Concise messages**: Get to the point quickly
3. **Reply appropriately**: Use Reply All only when necessary
4. **Attachment awareness**: Warn recipients about large attachments

### Security Best Practices

1. **Use encryption**: Enable PGP for sensitive communications
2. **Verify senders**: Check email headers when something seems suspicious
3. **Strong passwords**: Use unique, complex passwords
4. **Regular backups**: Ensure automatic backups are enabled

### Productivity Tips

1. **Keyboard shortcuts**: Learn shortcuts for common actions
2. **Folders and filters**: Organize mail automatically
3. **Saved searches**: Save frequent searches for quick access
4. **Batch operations**: Select multiple messages for bulk actions

---

## Getting Help

- **In-app Help**: Press `F1` or click **Help** > **unitMail Help**
- **Documentation**: https://docs.unitmail.org
- **Community Forum**: https://forum.unitmail.org
- **Issue Tracker**: https://github.com/unitmail/unitmail/issues
- **Email Support**: support@unitmail.org (for license holders)
