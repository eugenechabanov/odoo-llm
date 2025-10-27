# Q4: Shared Agent in Group Channel (Company Bookkeeper)

**Question:** For shared agents (multiple users talking to same AI in group), should we use mail.guest or fake email? Does this change our decision?

---

## The Requirement

From `LETTA_AGENT_ARCHITECTURE_PLAN.md`:

> **Company Bookkeeper Agent**
>
> Shared agent (bookkeeper) that multiple users can interact with, maintaining company-wide memory.
>
> - Single `mail.channel` = "Company Bookkeeper"
> - Multiple users can join channel
> - Single Letta agent instance for all users
> - Shared memory blocks (company SOPs, procedures)

**Key aspects:**
1. **Multiple users** in same channel
2. **Same AI** responds to all of them
3. **Shared memory** (company-wide knowledge)
4. Users see each other's conversations with AI
5. AI maintains context across all users

---

## Analysis: Does This Change the Decision?

### Scenario Breakdown

```python
# Create Company Bookkeeper channel
channel = env['discuss.channel'].create({
    'name': 'Company Bookkeeper',
    'channel_type': 'group',  # Multiple members
    'llm_enabled': True,
    'llm_assistant_id': bookkeeper_assistant.id,
    'llm_letta_agent_id': 'uuid-for-shared-agent',  # Single Letta agent
})

# Add multiple users
channel.add_members(partner_ids=[user1.id, user2.id, user3.id, ...])

# User 1: "What's our Q4 revenue?"
# AI responds (all users see it)

# User 2: "Show me invoice INV001"
# AI responds (all users see it)

# User 3: "Update our payment terms"
# AI responds (all users see it)
```

**Question:** Should AI be a member (mail.guest) or just a responder (fake email)?

---

## Option A: AI as mail.guest in Group

**Implementation:**
```python
# Create AI guest for bookkeeper
bookkeeper_guest = env['mail.guest'].create({
    'name': 'Company Bookkeeper',
    'is_ai': True,
    'llm_assistant_id': bookkeeper_assistant.id
})

# Add AI as member
channel = env['discuss.channel'].create({
    'channel_type': 'group',
    'channel_member_ids': [
        (0, 0, {'partner_id': user1.partner_id.id}),
        (0, 0, {'partner_id': user2.partner_id.id}),
        (0, 0, {'guest_id': bookkeeper_guest.id}),  # AI as member
    ]
})
```

**What you get:**

✅ **AI shows in member list**
```
Channel Members:
- John (Sales Manager)
- Sarah (CFO)
- Company Bookkeeper (AI) ← Shows up here
```

✅ **AI can have online status**
```
Company Bookkeeper (AI) • Online
```

✅ **Can @mention AI**
```
User: "@Company Bookkeeper what's our revenue?"
```

✅ **Feels like a "participant"**
- Users see AI as another member
- More intuitive for group setting

**Challenges:**

⚠️ **Settings changes**
- User switches from GPT-4 to Claude in channel settings
- Guest is still called "Company Bookkeeper" (name doesn't change)
- But underlying model changed
- Less transparent

⚠️ **Multiple shared agents**
- Company has both "Bookkeeper" and "Sales Assistant" shared channels
- Need 2 separate guests
- More complex to manage

---

## Option B: Fake Email in Group (Current Approach)

**Implementation:**
```python
# No AI member, just users
channel = env['discuss.channel'].create({
    'channel_type': 'group',
    'llm_enabled': True,
    'llm_assistant_id': bookkeeper_assistant.id,
    'channel_member_ids': [
        (0, 0, {'partner_id': user1.partner_id.id}),
        (0, 0, {'partner_id': user2.partner_id.id}),
    ]
})

# AI posts with fake email
channel.message_post(
    body=response,
    author_id=False,
    email_from="Company Bookkeeper <ai@bookkeeper.odoo>",
    llm_role='assistant'
)
```

**What you get:**

✅ **Transparent model usage**
- Email shows which model is responding
- If settings change, next message shows new model
- Clear history

✅ **Simpler code**
- No guest lifecycle
- No member management
- Just post messages

✅ **Flexible configuration**
- Users can change provider/model/tools
- Doesn't affect "who" is responding conceptually

**Trade-offs:**

❌ **AI not in member list**
```
Channel Members:
- John (Sales Manager)
- Sarah (CFO)
(AI not listed here)
```

❌ **No online status for AI**
- Can't show "AI is typing..."
- Can't show "AI is offline"

❌ **Can't @mention AI directly**
- Would need custom handling
- Or just assume all messages trigger AI

---

## Deep Dive: Group Channel Dynamics

### Who Triggers AI Response?

**Key question:** When does AI respond in a group channel?

**Option 1: AI responds to EVERY message**
```python
# Any user posts → AI responds
User1: "What's our revenue?"
AI: "Q4 revenue is $2M"

User2: "Thanks!"
AI: "You're welcome! How else can I help?" ← Annoying?
```
❌ **Problem:** AI responds to everything, even small talk

**Option 2: AI responds only when @mentioned**
```python
User1: "@Bookkeeper what's our revenue?"
AI: "Q4 revenue is $2M"

User2: "Wow, that's great" ← AI doesn't respond
```
✅ **Better:** Users control when AI engages

**Option 3: Smart triggering**
```python
# AI responds to questions, not statements
User1: "What's our revenue?" ← Question → AI responds
User2: "Thanks!" ← Statement → AI silent
User1: "@Bookkeeper update terms" ← @mention → AI responds
```
✅ **Best:** Intelligent, doesn't require @mention every time

---

## Verdict: Hybrid Approach? 🤔

### Recommendation: **Fake Email, BUT with smart features**

**Why:**
1. Keep simplicity of fake email (no guest management)
2. Add smart triggering (don't need @mention)
3. Add UI indicators (show "AI is thinking...")

**Implementation:**

```python
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def message_post(self, **kwargs):
        """After user posts, maybe trigger AI."""
        message = super().message_post(**kwargs)

        # In group channels with AI enabled
        if self.channel_type == 'group' and self.llm_enabled:
            # Check if should trigger AI
            if self._should_ai_respond(message):
                # Trigger async AI generation
                self.with_delay().llm_generate()

        return message

    def _should_ai_respond(self, message):
        """Decide if AI should respond to this message."""
        # Don't respond to AI's own messages
        if message.llm_role == 'assistant':
            return False

        # Respond if @mentioned (if we implement that)
        if self._is_ai_mentioned(message):
            return True

        # Respond to questions
        if self._is_question(message.body):
            return True

        # Otherwise, don't respond
        return False
```

---

## Member List & UI Considerations

### Option: Show AI in Member List (Without mail.guest)

**What if we fake the member list?**

```javascript
// Frontend: Patch channel model
const channelData = {...};
if (channelData.llm_enabled && channelData.llm_assistant_id) {
    // Add fake "AI member" to display
    channelData.members.push({
        id: `ai-${channelData.llm_assistant_id}`,
        name: channelData.llm_assistant_id.name,
        type: 'ai',
        status: 'online',  // Always online
        avatar: '/path/to/ai/avatar'
    });
}
```

**Benefits:**
- ✅ AI shows in UI member list
- ✅ No actual mail.guest in database
- ✅ Frontend-only addition
- ✅ Simpler backend

**Trade-offs:**
- ⚠️ Fake data (not in database)
- ⚠️ More frontend complexity
- ⚠️ But maybe worth it for UX?

---

## @Mention Support

### Can We Support @mention Without mail.guest?

**Yes! Custom handling:**

```python
# When user types "@Bookkeeper"
# Frontend: Parse and mark as llm_trigger
message = channel.message_post(
    body="@Bookkeeper what's our revenue?",
    llm_trigger=True  # Custom flag
)

# Backend: Check flag
def _should_ai_respond(self, message):
    # Check custom flag
    if message.llm_trigger:
        return True
    # ... other checks
```

**Implementation:**
1. Frontend: Autocomplete for AI name
2. Parse @AI in text
3. Set custom flag
4. Backend: Check flag and trigger AI

**Result:** @mention without mail.guest ✅

---

## Final Recommendation for Shared Agent

### Keep Fake Email Approach ✅

**BUT add enhancements:**

### 1. Smart Triggering
```python
def _should_ai_respond(self, message):
    """Intelligent decision on whether AI should respond."""
    # Skip AI's own messages
    if message.llm_role == 'assistant':
        return False

    # Skip system messages
    if message.message_type != 'comment':
        return False

    # For private channels (user + AI only)
    if self.channel_type == 'chat' and self.llm_enabled:
        return True  # Always respond in 1-on-1

    # For group channels
    if self.channel_type == 'group' and self.llm_enabled:
        # Check @mention (custom implementation)
        if self._is_ai_mentioned(message):
            return True

        # Check if message is a question
        if self._is_question(message.body):
            return True

        # Otherwise don't respond (avoid spam)
        return False

    return False
```

### 2. UI Enhancements (Frontend)
```javascript
// Show AI in member list (fake member)
// Show "AI is thinking..." while generating
// Support @AI autocomplete
```

### 3. Email From Logic
```python
def _llm_get_email_from(self):
    """Smart email generation."""
    if self.llm_assistant_id:
        # Shared agent: Use assistant name
        return f"{self.llm_assistant_id.name} <ai@assistant.odoo>"
    elif self.llm_model_id:
        # Custom config: Use model name
        return f"{self.llm_model_id.name} <ai@{self.llm_provider_id.name}.ai>"
    else:
        return "AI <ai@odoo.ai>"
```

---

## CRITICAL PROBLEMS IDENTIFIED ⚠️

### Problem 1: What IS a "Shared Assistant"?

**Two interpretations:**

#### Option A: Shared Channel (SIMPLE)
```python
# Multiple users in ONE channel with AI
# ONE channel = ONE Letta agent instance
channel = env['discuss.channel'].create({
    'name': 'Company Bookkeeper',
    'llm_letta_agent_id': 'uuid-123',  # Single agent
})
# Users: Alice, Bob, Carol all in same channel
# They ALL see each other's messages
```
✅ **This is what we assumed so far**

#### Option B: Shared Agent Template (COMPLEX)
```python
# Multiple users, EACH has private channel
# But ALL channels use SAME Letta agent instance with SHARED memory
channel_alice = env['discuss.channel'].create({
    'name': 'Alice <> Bookkeeper',
    'llm_letta_agent_id': 'uuid-123',  # Same agent UUID
})
channel_bob = env['discuss.channel'].create({
    'name': 'Bob <> Bookkeeper',
    'llm_letta_agent_id': 'uuid-123',  # Same agent UUID
})
# Alice and Bob don't see each other's messages
# But Letta agent remembers BOTH conversations
```
❌ **This is much more complex - needs different architecture**

**QUESTION FOR USER:** Which interpretation is correct?

For now, analyzing **Option A** (shared channel).

---

### Problem 2: Permission Isolation (CRITICAL SECURITY ISSUE 🔴)

**Scenario:**
```python
# Channel members:
# - Alice (Admin) - can see all invoices
# - Bob (Sales) - can only see customer invoices
# - Carol (Accountant) - can see financial records

# Alice asks: "Show me employee salary for Bob"
# AI responds with salary information
# Bob sees the message! ← PRIVACY VIOLATION
```

**Current implementation:**
```python
# From llm_thread.py
def generate(self):
    with self._generation_lock():
        # AI runs with self.user_id permissions (thread owner)
        # In shared channel: whose permissions?
```

**Problem:** In group channel, there's no single "owner". Who's permissions does AI use?

**Solutions:**

#### Solution 2A: AI Runs with Message Author Permissions ✅
```python
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)

        if self.channel_type == 'group' and self.llm_enabled:
            if self._should_ai_respond(message):
                # Pass current user context
                self.with_context(
                    llm_current_user_id=self.env.user.id
                ).with_delay().generate()

        return message

    def generate(self):
        # Get user who triggered this
        user_id = self.env.context.get('llm_current_user_id')
        if user_id:
            user = self.env['res.users'].browse(user_id)
            # Run tools with THIS user's permissions
            self.sudo(user).generate_messages()
```

**Result:** AI only has access to data the requesting user can see ✅

#### Solution 2B: Dedicated AI User with Minimal Permissions ⚠️
```python
# Create special "AI User" with restricted permissions
ai_user = env['res.users'].create({
    'name': 'AI Assistant',
    'groups_id': [(6, 0, [basic_user_group.id])],
})

# AI always runs as this user
def generate(self):
    self.sudo(ai_user).generate_messages()
```

**Problem:** AI can only access public data. Can't help with user-specific queries.

#### Solution 2C: Response Filtering (COMPLEX) ❌
- AI generates with admin permissions
- Filter response per user before displaying
- Too complex, error-prone

**RECOMMENDATION:** Solution 2A - Run with message author permissions ✅

---

### Problem 3: Concurrent Generation (RACE CONDITION 🔴)

**Scenario:**
```python
# 10:00:00 - Alice: "What's our Q4 revenue?"
# 10:00:01 - AI starts generating (takes 5 seconds)
# 10:00:03 - Bob: "Show me invoice INV001" ← While AI is still working
```

**Current protection:**
```python
def _acquire_thread_lock(self):
    """Acquire PostgreSQL advisory lock for this thread."""
    query = "SELECT pg_try_advisory_lock(%s)"
    self.env.cr.execute(query, (self.id,))
    result = self.env.cr.fetchone()

    if not result or not result[0]:
        raise UserError(
            _("Thread is currently generating a response. Please wait.")
        )
```

**Problem:** Bob gets an error! Bad UX in group chat.

**Solutions:**

#### Solution 3A: Message Queue (RECOMMENDED ✅)
```python
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    llm_generation_queue = fields.One2many('llm.generation.queue', 'channel_id')
    llm_is_generating = fields.Boolean(compute='_compute_is_generating')

    def _should_ai_respond(self, message):
        # Always queue, never reject
        return True

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)

        if self.channel_type == 'group' and self.llm_enabled:
            if self._should_ai_respond(message):
                # Add to queue
                self.env['llm.generation.queue'].create({
                    'channel_id': self.id,
                    'message_id': message.id,
                    'user_id': self.env.user.id,
                    'state': 'pending',
                })

                # Process queue if not busy
                if not self.llm_is_generating:
                    self._process_generation_queue()

        return message

    def _process_generation_queue(self):
        """Process queued generation requests one by one."""
        queue = self.llm_generation_queue.filtered(
            lambda q: q.state == 'pending'
        ).sorted('create_date')

        if not queue:
            return

        for item in queue:
            try:
                item.state = 'processing'
                # Generate with user's permissions
                self.with_context(
                    llm_current_user_id=item.user_id.id,
                    llm_trigger_message_id=item.message_id.id,
                ).generate()
                item.state = 'done'
            except Exception as e:
                item.state = 'error'
                item.error_message = str(e)
```

**UI Enhancement:**
```javascript
// Show queue status
"AI is responding to Alice's question... (Bob's question is queued)"
```

#### Solution 3B: Prevent Mentions While Busy ⚠️
```python
# Frontend: Disable @AI mention while generating
if (thread.llm_is_generating) {
    // Show: "AI is thinking, please wait..."
    // Disable @AI autocomplete
}
```

**Problem:** Users can still post messages, just can't trigger AI. Confusing.

**RECOMMENDATION:** Solution 3A - Queue all requests ✅

---

### Problem 4: Context Confusion (MULTIPLE CONVERSATION THREADS 🔴)

**Scenario:**
```python
# 10:00 - Alice: "What's our Q4 revenue?"
# 10:01 - AI: "Q4 revenue is $2M"
# 10:02 - Bob: "Show me invoice INV001"
# 10:03 - AI: "Here's INV001..."
# 10:04 - Carol: "Can you break that down by month?" ← Which one? Revenue or invoice?
```

**Problem:** AI has no way to know Carol is referring to Alice's revenue question vs Bob's invoice.

**Current implementation:**
```python
def get_llm_messages(self):
    """Get ALL messages in thread for context."""
    return self.message_ids.filtered(
        lambda m: m.llm_role in ['user', 'assistant']
    ).sorted('create_date')
```

**All messages go to AI → AI tries to maintain ALL conversation threads → Confusion!**

**Solutions:**

#### Solution 4A: Require @AI Mention with Context (SIMPLE ✅)
```python
# Users MUST @mention AI and be explicit
# Carol: "@AI can you break down the revenue by month?"
#        ^    ^ explicit reference

def _should_ai_respond(self, message):
    # For group channels: ONLY respond to @mentions
    if self.channel_type == 'group':
        return self._is_ai_mentioned(message)

    # For private: respond to everything
    return True
```

**Benefit:** Forces users to be explicit, reduces confusion

**Trade-off:** Every message must @mention AI (annoying)

#### Solution 4B: Smart Context Windows (AI DECIDES 🤖)
```python
def get_llm_messages(self):
    """Get recent context window, let AI figure it out."""
    # Last N messages (e.g., 20)
    messages = self.message_ids.sorted('create_date')[-20:]

    # System message to AI
    system_msg = """
    You are in a group chat with multiple users.
    Multiple conversation threads may be happening.
    When responding, reference WHO you're responding to.
    Example: "Regarding Alice's question about revenue..."
    """

    return messages
```

**Benefit:** AI handles multi-threading naturally

**Trade-off:** Depends on AI intelligence, may still confuse

#### Solution 4C: Thread-per-User in Group (COMPLEX ❌)
```python
# Each user's messages create separate "sub-threads"
# AI maintains separate context per user
# Too complex for shared memory use case
```

**RECOMMENDATION:** Solution 4A for MVP, 4B for future enhancement ✅

---

### Problem 5: User-to-User vs User-to-AI Messages

**Scenario:**
```python
# Alice: "Hey Bob, did you see the report?"
# Bob: "Yes, looks great!"
# Alice: "@AI what's our conversion rate?"
```

**Question:** Should AI see "Hey Bob" messages?

**Options:**

#### Option 5A: AI Sees Everything
```python
# All messages go to AI
# Pro: Full context
# Con: AI might respond to chitchat
```

#### Option 5B: AI Only Sees @Mentions
```python
def get_llm_messages(self):
    # Only messages that mentioned AI
    return self.message_ids.filtered(
        lambda m: m.llm_role in ['user', 'assistant'] or
                  self._message_mentions_ai(m)
    )
```

**RECOMMENDATION:** Option 5B - Only show AI-relevant messages ✅

---

## Updated Architecture for Shared Agent

### Definition (Option A - Shared Channel)

**What is a shared assistant:**
- ONE group channel
- Multiple users are members
- ONE Letta agent instance (shared memory)
- All users see all messages
- AI responds to @mentions

### Required Fields

```python
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # LLM fields (from mail.thread extension)
    llm_enabled = fields.Boolean(default=False)
    llm_assistant_id = fields.Many2one('llm.assistant')
    llm_letta_agent_id = fields.Char()  # Letta agent UUID

    # Queue management
    llm_generation_queue = fields.One2many('llm.generation.queue', 'channel_id')
    llm_is_generating = fields.Boolean(compute='_compute_is_generating')

class LLMGenerationQueue(models.Model):
    _name = 'llm.generation.queue'
    _order = 'create_date ASC'

    channel_id = fields.Many2one('discuss.channel', required=True)
    message_id = fields.Many2one('mail.message', required=True)
    user_id = fields.Many2one('res.users', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='pending')
    error_message = fields.Text()
```

### Smart Triggering Logic

```python
def _should_ai_respond(self, message):
    """Decide if AI should respond."""
    # Skip AI's own messages
    if message.llm_role == 'assistant':
        return False

    # Skip system messages
    if message.message_type != 'comment':
        return False

    # For private channels: always respond
    if self.channel_type == 'chat' and self.llm_enabled:
        return True

    # For group channels: ONLY @mentions (MVP approach)
    if self.channel_type == 'group' and self.llm_enabled:
        return self._is_ai_mentioned(message)

    return False

def _is_ai_mentioned(self, message):
    """Check if AI was @mentioned in message."""
    # Option 1: Check for @AI in body
    if not message.body:
        return False

    # Parse body for @mentions
    # Could check for assistant name or generic "@AI"
    assistant_name = self.llm_assistant_id.name if self.llm_assistant_id else "AI"
    return f"@{assistant_name}" in message.body or "@AI" in message.body.upper()
```

### Permission-Aware Generation

```python
def message_post(self, **kwargs):
    """Override to handle AI triggering with user context."""
    message = super().message_post(**kwargs)

    if self.channel_type == 'group' and self.llm_enabled:
        if self._should_ai_respond(message):
            # Queue generation with current user context
            self.env['llm.generation.queue'].create({
                'channel_id': self.id,
                'message_id': message.id,
                'user_id': self.env.user.id,  # Current user
            })

            # Process queue if not busy
            if not self.llm_is_generating:
                self.with_delay()._process_generation_queue()

    return message

def generate(self):
    """Generate with proper user permissions."""
    self.ensure_one()

    # Get user context from queue item
    user_id = self.env.context.get('llm_current_user_id')

    if not user_id:
        raise UserError(_("No user context for AI generation"))

    user = self.env['res.users'].browse(user_id)

    # Run generation with THIS user's permissions
    with self._generation_lock():
        # Switch to user's context
        channel_as_user = self.sudo(user)
        return channel_as_user.generate_messages()
```

### Summary Table

| Problem | Solution | Trade-off |
|---------|----------|-----------|
| **Permission Isolation** | Run AI with message author's permissions | AI can only access what user can see |
| **Concurrent Generation** | Message queue system | Slight delay if multiple requests |
| **Context Confusion** | Require @AI mentions in groups | Users must explicitly mention AI |
| **User-to-User Chat** | AI only sees @mentioned messages | Better focus, less noise |
| **AI Representation** | Fake email (from Q3) | No guest management needed |

### Benefits

✅ **Secure:** Permission isolation per user
✅ **Scalable:** Queue handles concurrent requests
✅ **Clear:** @mentions make intent explicit
✅ **Simple:** No complex threading logic needed
✅ **Flexible:** Works for private and group channels

### Constraints

⚠️ **Users must @mention AI** in group channels
⚠️ **Only one generation at a time** per channel
⚠️ **AI can't proactively respond** to non-mentioned messages
⚠️ **Shared memory with permission boundaries** (Letta sees all, but tools respect permissions)

---

## Open Questions

1. **Shared assistant definition:** Option A (shared channel) or Option B (shared agent instance across private channels)?
2. **Letta memory isolation:** How does Letta handle permission-aware tool execution?
3. **Queue timeout:** How long should queued requests wait before expiring?
4. **UI for queue:** How to show "2 questions ahead of you" to users?
5. **@mention syntax:** `@AI`, `@Bookkeeper`, or `@Company Bookkeeper`?
