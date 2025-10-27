# Q&A - LLM Thread to Mail.Thread Architecture Discussion

**Date Started:** 2025-10-24
**Participants:** Saiful Islam, Claude (AI Assistant)

---

## Q1: How to keep channel private, public, or between only one user and AI?

**Asked:** 2025-10-24

**Answer:**

Odoo's `discuss.channel` has built-in privacy control via `channel_type` field:

### 1. Private (Just Me + AI) - `channel_type='chat'`
```python
channel = env['discuss.channel'].create({
    'name': 'My AI Assistant',
    'channel_type': 'chat',  # Private chat
    'llm_enabled': True,
})
```
- Only you can see it
- Perfect for personal AI assistant

### 2. Private Group (Team + AI) - `channel_type='group'`
```python
channel = env['discuss.channel'].create({
    'name': 'Team AI',
    'channel_type': 'group',  # Private group
    'llm_enabled': True,
    'channel_member_ids': [...],  # Invite specific users
})
```
- Only invited members can see it
- Good for shared AI like company bookkeeper

### 3. Public (Anyone + AI) - `channel_type='channel'`
```python
channel = env['discuss.channel'].create({
    'name': 'Public AI',
    'channel_type': 'channel',  # Public
    'llm_enabled': True,
    'group_public_id': env.ref('base.group_user'),
})
```
- Anyone with permissions can join

**Key Point:** LLMs are NOT Odoo users. They're automatic responses to messages. No actual "AI user" exists in the system.

---

<!-- Future Q&A entries will be added here when requested -->
