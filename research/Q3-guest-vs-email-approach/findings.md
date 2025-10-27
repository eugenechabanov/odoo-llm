# Q3: AI as mail.guest vs Fake Email Author

**Question:** Should AI be a mail.guest member OR just post with fake email? What are the use cases and trade-offs?

---

## The Use Cases (Your Requirements)

### Use Case 1: User Creates Chat with Assistant Template
```python
# User clicks "New Chat" → Selects "Sales Assistant" template
channel = create_chat_with_assistant(user, assistant_template)
# → Gets: provider, model, tools, system prompt pre-configured
# → But user can change these settings in the channel
```

### Use Case 2: User Creates Custom Chat
```python
# User clicks "New Chat" → Manually selects provider + model + tools
channel = create_custom_chat(
    user=user,
    provider=anthropic,
    model=claude_sonnet,
    tools=[search_tool, calculator_tool]
)
# → No assistant template, just direct configuration
```

### Use Case 3: User Changes Settings Mid-Conversation
```python
# User is chatting, then changes:
channel.llm_model_id = different_model
channel.llm_tool_ids = [(6, 0, [new_tool_ids])]
# → Conversation continues with new settings
# → AI should adapt
```

---

## Analysis: Two Approaches

### Approach A: AI as mail.guest (Channel Member)

**How it works:**
```python
# Create AI guest for each assistant template
ai_guest = env['mail.guest'].create({
    'name': assistant.name,
    'is_ai': True,
    'llm_assistant_id': assistant.id
})

# Add as channel member
channel.add_members(guest_ids=[ai_guest.id])

# AI posts as guest
channel.with_context(guest=ai_guest).message_post(
    body=response,
    author_guest_id=ai_guest.id
)
```

**Problems with Use Case 1-3:**

❌ **Problem 1: One guest per assistant template**
- If user uses "Sales Assistant" → creates guest for Sales Assistant
- If user switches to "Support Assistant" → need different guest?
- What about the old guest? Remove it?

❌ **Problem 2: Custom chats (no assistant)**
- User selects provider + model directly (no template)
- Which guest do we use? Create anonymous "AI" guest?
- Gets messy

❌ **Problem 3: Changing settings**
- User changes from GPT-4 to Claude
- Guest is still called "GPT-4 Assistant"?
- Or do we create new guest and swap members?

❌ **Problem 4: Multiple channels, same assistant**
- User has 3 chats all using "Sales Assistant"
- Do we create 3 guests? Or share 1 guest?
- If shared, guest appears in all 3 channels
- Confusing for UI

---

### Approach B: AI as Fake Email Author (Current)

**How it works:**
```python
# No guest created, just post with email
channel.message_post(
    body=response,
    author_id=False,
    email_from=f"{model.name} <ai@{provider.name}.ai>",
    llm_role='assistant'
)
```

**Benefits for Use Case 1-3:**

✅ **Benefit 1: No member management**
- Channel just has the user
- AI is not a "member", it's just a responder
- Cleaner mental model

✅ **Benefit 2: Works with any configuration**
- Assistant template? → Email shows assistant name
- Custom (provider + model)? → Email shows model name
- Easy to adapt email_from dynamically

✅ **Benefit 3: Settings changes just work**
- User switches from GPT-4 to Claude?
- Next message shows "Claude <ai@openai.ai>"
- Previous messages still show "GPT-4 <ai@openai.ai>"
- Clear history of what was used

✅ **Benefit 4: Simpler code**
- No guest lifecycle management
- No "which guest" logic
- Just format email_from correctly

---

## When Would mail.guest Make Sense?

### Scenario A: Live Chat (Website Visitor)

**Use case:** Anonymous website visitor chats with AI, then human operator joins

```python
# Visitor arrives (already a guest)
visitor_guest = env['mail.guest'].create({
    'name': 'Anonymous Visitor',
    'is_ai': False  # Real human
})

# Create channel: visitor + AI
channel = env['discuss.channel'].create({
    'channel_type': 'chat',
    'llm_enabled': True,
    'channel_member_ids': [
        (0, 0, {'guest_id': visitor_guest.id}),  # Visitor
        # AI posts with fake email, not as guest
    ]
})

# Later: Human operator joins
channel.add_members(partner_ids=[operator.partner_id.id])
```

**Here:** Visitor is guest (makes sense), but AI still uses fake email

---

### Scenario B: AI Needs to "Be Present" in Channel

**If we want:**
- AI to show in member list
- AI to have online/offline status
- AI to receive @mentions
- AI to "leave" channel

**Then mail.guest makes sense**

**But for your use case:** None of these seem needed
- User knows it's AI (it's an AI chat!)
- AI always "responds" (no online/offline concept)
- AI doesn't need to "leave"
- @mentions not relevant (it's just you and AI)

---

## Recommendation

### For Your Use Cases: Stick with Fake Email ✅

**Why:**
1. **Flexible configuration** - Settings can change, email_from adapts
2. **No guest lifecycle** - No creating/deleting/swapping guests
3. **Clear message history** - See which model/provider was used per message
4. **Simpler code** - Less moving parts
5. **Works everywhere** - discuss.channel, chatter, any record

**Implementation:**
```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _llm_get_email_from(self):
        """Generate email_from for AI messages."""
        self.ensure_one()

        if self.llm_assistant_id:
            # Use assistant name
            return f"{self.llm_assistant_id.name} <ai@assistant.odoo>"
        elif self.llm_model_id:
            # Use model name
            provider = self.llm_provider_id.name.lower().replace(' ', '')
            return f"{self.llm_model_id.name} <ai@{provider}.ai>"
        else:
            # Fallback
            return "AI Assistant <ai@odoo.ai>"

    def message_post(self, **kwargs):
        """Override to set email_from for AI messages."""
        llm_role = kwargs.get('llm_role')

        if llm_role == 'assistant' and not kwargs.get('author_id'):
            kwargs['email_from'] = self._llm_get_email_from()

        return super().message_post(**kwargs)
```

**Example usage:**
```python
# User creates chat with assistant
channel = env['discuss.channel'].create({
    'name': 'Sales Chat',
    'channel_type': 'chat',
    'llm_enabled': True,
    'llm_assistant_id': sales_assistant.id,  # Has provider, model, tools
    'channel_member_ids': [(0, 0, {'partner_id': user.partner_id.id})]
})

# AI responds (no guest needed)
channel.message_post(
    body="How can I help with sales?",
    llm_role='assistant'
)
# → Shows as: "Sales Assistant <ai@assistant.odoo>"

# User changes to different model
channel.llm_model_id = claude_model

# AI responds again
channel.message_post(
    body="I'm now using Claude!",
    llm_role='assistant'
)
# → Shows as: "Claude Sonnet <ai@anthropic.ai>"
# → Previous messages still show old model name
```

---

## Edge Case: mail.guest for Special Scenarios

**When you MIGHT want mail.guest:**

### Scenario: Multiple AI Assistants in Same Channel

```python
# Group chat: User + Sales AI + Support AI
channel = env['discuss.channel'].create({
    'channel_type': 'group',
    'channel_member_ids': [
        (0, 0, {'partner_id': user.partner_id.id}),
        (0, 0, {'guest_id': sales_ai_guest.id}),
        (0, 0, {'guest_id': support_ai_guest.id}),
    ]
})

# User: "I need help with an order"
# Sales AI responds
# Support AI responds
# They can both "see" each other's messages
```

**This is very advanced** - probably not needed for MVP

---

## Summary Table

| Aspect | mail.guest | Fake Email (Current) |
|--------|------------|---------------------|
| **Use Case 1: Assistant Template** | ⚠️ Need to manage guest per template | ✅ Just format email_from |
| **Use Case 2: Custom Config** | ❌ Which guest to use? | ✅ Format from model name |
| **Use Case 3: Change Settings** | ❌ Need to swap guests? | ✅ Next message shows new settings |
| **Multiple Channels** | ⚠️ Share guest or create per channel? | ✅ No problem |
| **Member List UI** | ✅ AI shows in members | ❌ AI not in members (but do you need it?) |
| **Online Status** | ✅ Can show online/offline | ❌ Not applicable |
| **@Mentions** | ✅ Can @mention AI | ❌ Can't @mention |
| **Code Complexity** | ❌ Complex guest management | ✅ Simple email formatting |
| **Flexibility** | ❌ Rigid (one guest per config) | ✅ Dynamic (changes with settings) |

---

## Final Recommendation

### For your requirements: **Keep fake email approach** ✅

**Reasons:**
1. User can change provider/model/tools freely
2. Message history shows what was used
3. No guest lifecycle to manage
4. Works in discuss.channel AND chatter AND any record
5. Simpler, more flexible

**When to consider mail.guest:**
- If you need AI in member list
- If you need online/offline status
- If you need multiple AI assistants in same channel
- If you need @mention functionality

**For now:** None of these seem like requirements

**Implementation:** Extend your current `_get_llm_email_from()` method to be smarter:
```python
def _llm_get_email_from(self):
    # Check assistant first
    if self.llm_assistant_id:
        return f"{self.llm_assistant_id.name} <ai@assistant.odoo>"

    # Then check model
    if self.llm_model_id and self.llm_provider_id:
        provider = self.llm_provider_id.name.lower().replace(' ', '')
        return f"{self.llm_model_id.name} <ai@{provider}.ai>"

    # Fallback
    return "AI <ai@odoo.ai>"
```

Simple, flexible, works! ✅
