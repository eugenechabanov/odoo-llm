# Q2: discuss.channel Compatibility & AI as "Guest"

**Question:** How does discuss.channel work? Can we create DM with AI (non-user)?

---

## Short Answer

**Yes! Use `mail.guest` for AI** ✅

Odoo already has a perfect pattern for "anonymous users" in channels - **`mail.guest`**. We can reuse this for AI!

---

## Key Findings

### 1. discuss.channel vs mail.channel

**In Odoo 18.0:**
- ✅ **`discuss.channel`** is the ONLY model (it's `_name = 'discuss.channel'`)
- ❌ **`mail.channel`** does NOT exist anymore (renamed in Odoo 18)
- ✅ **`discuss.channel`** inherits `mail.thread` (perfect for our extension!)

**Code Evidence:**
```python
# File: addons/mail/models/discuss/discuss_channel.py
class Channel(models.Model):
    _name = 'discuss.channel'
    _inherit = ["mail.thread", "bus.listener.mixin"]

    channel_type = fields.Selection([
        ('chat', 'Chat'),       # 1-on-1 private
        ('channel', 'Channel'), # Public/semi-public
        ('group', 'Group')      # Private group
    ])
```

---

### 2. Channel Members: Partners OR Guests

**Important Discovery:** Channels can have TWO types of members:

```python
# File: addons/mail/models/discuss/discuss_channel_member.py
class ChannelMember(models.Model):
    _name = "discuss.channel.member"

    partner_id = fields.Many2one("res.partner")  # For logged-in users
    guest_id = fields.Many2one("mail.guest")     # For anonymous/guests
```

**This means:**
- **Users** → Have `partner_id` (linked to res.users)
- **Guests** → Have `guest_id` (NOT linked to users)
- **AI** → Can be a GUEST! ✅

---

### 3. mail.guest - Perfect for AI!

**What is mail.guest?**

```python
# File: addons/mail/models/discuss/mail_guest.py
class MailGuest(models.Model):
    _name = 'mail.guest'

    name = fields.Char(required=True)              # "AI Assistant"
    access_token = fields.Char(required=True)      # Auth token
    channel_ids = fields.Many2many('discuss.channel')  # Channels they're in
    im_status = fields.Char()                      # online/offline/away
```

**Key Properties:**
- ✅ Has a name (can be "AI Assistant", "Claude", etc.)
- ✅ Can be in multiple channels
- ✅ Has online/offline status
- ✅ NOT a real user (no login, no permissions)
- ✅ Can post messages
- ✅ Perfect for AI!

---

### 4. How Guests Work in Channels

**Creation Pattern:**
```python
# Create a guest (AI)
ai_guest = env['mail.guest'].create({
    'name': 'AI Assistant',
    'country_id': False,  # No country
    'lang': 'en_US',
    'timezone': 'UTC'
})

# Create a private chat with AI
channel = env['discuss.channel'].create({
    'name': 'Chat with AI',
    'channel_type': 'chat',  # 1-on-1
    'channel_member_ids': [
        (0, 0, {'partner_id': user.partner_id.id}),  # Real user
        (0, 0, {'guest_id': ai_guest.id})             # AI guest
    ]
})
```

**Result:** Private DM between user and AI ✅

---

### 5. Constraints to Consider

**From channel_member constraints:**
```python
@api.constrains('partner_id')
def _contrains_no_public_member(self):
    for member in self:
        if any(user._is_public() for user in member.partner_id.user_ids):
            raise ValidationError(_("Channel members cannot include public users."))
```

**Important:**
- ❌ Public users CANNOT be channel members
- ✅ Guests CAN be channel members (different from public users)
- ✅ AI as guest is perfectly valid

---

### 6. Channel Types Explained

```python
channel_type = fields.Selection([
    ('chat', 'Chat'),       # Private, 1-on-1
    ('channel', 'Channel'), # Public/semi-public
    ('group', 'Group')      # Private group, multiple members
])
```

**For AI:**
- **`chat`** - Private DM with AI (user + AI guest)
- **`group`** - Group chat with AI (multiple users + AI guest)
- **`channel`** - Public channel with AI (anyone + AI guest)

---

## How This Fits With Our Extension

### Our Extension on mail.thread

```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    llm_enabled = fields.Boolean(default=False)
    llm_provider_id = fields.Many2one('llm.provider')
    # ... other fields
```

### discuss.channel Already Inherits mail.thread

```python
class Channel(models.Model):
    _name = 'discuss.channel'
    _inherit = ["mail.thread", ...]  # ← Gets llm_enabled automatically!
```

**Result:**
- ✅ discuss.channel automatically gets all our LLM fields
- ✅ No special inheritance needed
- ✅ Works out of the box!

---

## Reusing Existing Patterns

### Pattern 1: Creating AI as Guest

```python
# In llm_assistant module or similar:
def _get_or_create_ai_guest(self, assistant):
    """Get or create a mail.guest for this AI assistant."""
    # Search for existing guest
    ai_guest = self.env['mail.guest'].search([
        ('name', '=', f'AI: {assistant.name}')
    ], limit=1)

    if not ai_guest:
        ai_guest = self.env['mail.guest'].create({
            'name': f'AI: {assistant.name}',
            'lang': 'en_US',
            'timezone': 'UTC',
            # Could store assistant reference in context or custom field
        })

    return ai_guest
```

### Pattern 2: Creating AI Chat Channel

```python
def create_ai_chat(self, user, assistant):
    """Create a private chat between user and AI assistant."""
    # Get AI guest
    ai_guest = self._get_or_create_ai_guest(assistant)

    # Create channel
    channel = self.env['discuss.channel'].create({
        'name': f'Chat with {assistant.name}',
        'channel_type': 'chat',
        'llm_enabled': True,  # Our extension field!
        'llm_assistant_id': assistant.id,  # Our extension field!
        'channel_member_ids': [
            (0, 0, {'partner_id': user.partner_id.id}),
            (0, 0, {'guest_id': ai_guest.id})
        ]
    })

    return channel
```

### Pattern 3: AI Posting Messages

```python
def _post_ai_response(self, channel, response_text):
    """AI guest posts a message to the channel."""
    ai_guest = channel.channel_member_ids.filtered('guest_id').guest_id

    channel.with_context(guest=ai_guest).message_post(
        body=response_text,
        author_guest_id=ai_guest.id,  # Message from AI guest
        llm_role='assistant',  # Our extension param
        message_type='comment'
    )
```

---

## Benefits of This Approach

### ✅ Reuses Existing Infrastructure

- Guest model already exists
- Guest members already work
- Guest presence (online/offline) already works
- Guest authentication already works
- UI already renders guests

### ✅ No Need for Fake Users

- Don't create res.users for AI
- Don't manage user permissions
- Don't deal with authentication
- Clean separation: users vs guests

### ✅ Works in Discuss App

- Guests show up in member lists
- Guests can "post" messages (we post on their behalf)
- Guests have avatars
- Guests have online status

### ✅ Perfect for Live Chat

```python
# Live chat visitor becomes guest
visitor_guest = env['mail.guest'].create({...})

# Create channel with visitor + AI
channel = env['discuss.channel'].create({
    'channel_type': 'chat',
    'llm_enabled': True,
    'channel_member_ids': [
        (0, 0, {'guest_id': visitor_guest.id}),  # Website visitor
        (0, 0, {'guest_id': ai_guest.id})        # AI assistant
    ]
})

# AI responds automatically
# Human operator can join later if needed
```

---

## Potential Issues & Solutions

### Issue 1: Guest Authentication

**Problem:** Guests need access_token for authentication

**Solution:**
- Create token when creating AI guest
- Store token securely
- Use for posting messages on AI's behalf

### Issue 2: Guest Permissions

**Problem:** Guests have limited permissions

**Solution:**
- Use `sudo()` when AI needs to post messages
- Wrap AI operations in proper permission context
- AI operations run with system permissions

### Issue 3: Identifying AI Guests

**Problem:** How to distinguish AI guests from human guests?

**Solution 1:** Naming convention
```python
name = f'AI: {assistant.name}'  # Prefix with "AI:"
```

**Solution 2:** Custom field (extend mail.guest)
```python
class MailGuest(models.Model):
    _inherit = 'mail.guest'

    is_ai = fields.Boolean(default=False)
    llm_assistant_id = fields.Many2one('llm.assistant')
```

---

## Summary

### What We Know:

1. ✅ **discuss.channel** is the only model (mail.channel doesn't exist in 18.0)
2. ✅ **discuss.channel** inherits **mail.thread** (our extension works automatically)
3. ✅ **mail.guest** exists for anonymous users (perfect for AI)
4. ✅ Channels can have **partner_id OR guest_id** members
5. ✅ Guests can post messages, have status, have avatars

### What We Can Do:

1. ✅ Create AI as **mail.guest**
2. ✅ Create private chats between user and AI guest
3. ✅ Create group chats with multiple users + AI guest
4. ✅ AI posts messages as guest (using `author_guest_id`)
5. ✅ Reuse all existing Discuss UI for guests

### What We Should Do:

**Extend mail.guest for AI:**
```python
class MailGuest(models.Model):
    _inherit = 'mail.guest'

    is_ai = fields.Boolean(default=False)
    llm_assistant_id = fields.Many2one('llm.assistant')
```

**Then channels automatically work:**
```python
# User wants to chat with AI
channel = env['discuss.channel'].create({
    'channel_type': 'chat',
    'llm_enabled': True,
    'channel_member_ids': [
        (0, 0, {'partner_id': user.partner_id.id}),
        (0, 0, {'guest_id': ai_guest.id})
    ]
})
```

**Perfect compatibility!** ✅
