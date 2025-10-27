# Letta Agent Architecture - Action Plan

**Meeting Date:** October 21, 2025
**Participants:** Alexey Yushin, Saiful Islam
**Document Created:** October 24, 2025

## Executive Summary

This document outlines architectural improvements to Odoo LLM to enable better integration with Letta agents, support for shared memory blocks, and flexible deployment patterns including live chat integration and multi-user agent conversations.

## Core Architectural Problem

### Current Architecture
```
Contact/Object
    ↓
LLM Thread (intermediate model)
    ↓
Mail Messages
```

**Issue:** LLM Thread is an anti-pattern in Odoo because:
- It creates an intermediate layer between objects and messages
- Messages in Odoo are typically linked directly to objects via `mail.thread` mixin
- Doesn't align with Odoo's standard discuss/channel architecture

### Odoo's Standard Pattern
```
Contact/Object (inherits mail.thread)
    ↓
Mail Messages (directly linked)
```

OR

```
Mail Channel (is a record, inherits mail.thread)
    ↓
Mail Messages (linked to channel)
```

## Proposed Architecture Changes

### 1. LLM Thread as Mixin

**Goal:** Make `llm.thread` work like `mail.thread` - as a mixin that can be added to any model.

**Benefits:**
- Aligns with Odoo architectural patterns
- Allows direct message linking to objects
- Enables flexible deployment on mail.channel, custom models, or business objects

**Implementation Options:**

#### Option A: LLM Thread as Pure Mixin
```python
class LLMThreadMixin(models.AbstractModel):
    _name = 'llm.thread.mixin'
    _inherit = ['mail.thread']

    # LLM-specific fields
    llm_provider_id = fields.Many2one('llm.provider')
    llm_model_id = fields.Many2one('llm.model')
    llm_assistant_id = fields.Many2one('llm.assistant')

    # Methods for LLM conversation management
```

Usage scenarios:
1. **Direct on business objects:** `res.partner` inherits `llm.thread.mixin`
2. **On mail.channel:** Extend discuss channels with LLM capabilities
3. **Separate model:** Keep current `llm.thread` model for many-to-one relationships

#### Option B: Hybrid Approach
- Keep `llm.thread` as a model for many-to-one scenarios
- Create `llm.thread.mixin` for direct integration scenarios
- Both share common functionality via abstract base

### 2. Mail Channel Extension

**Goal:** Enable LLM conversations directly on `mail.channel` for discuss-style interactions.

**Use Cases:**
- Company-wide agents (bookkeeper, project manager)
- Multi-user conversations with shared context
- Live chat with AI assistance

**Implementation:**
```python
class MailChannel(models.Model):
    _inherit = 'mail.channel'

    # Option to enable LLM on channel
    llm_enabled = fields.Boolean()
    llm_assistant_id = fields.Many2one('llm.assistant')
    llm_letta_agent_id = fields.Char()  # Letta agent UUID

    # Control flag for AI vs manual
    llm_manual_override = fields.Boolean()
```

## Use Case Requirements

### Use Case 1: Live Chat with AI Agent

**Scenario:** User visits website, starts live chat, AI responds until escalation needed.

**Requirements:**
1. New live chat session creates `mail.channel`
2. Channel linked to Letta agent template (from assistant)
3. User messages → relayed to Letta → responses back to channel
4. "Escalate to human" tool sets `llm_manual_override = True`
5. Human operator takes over, messages NOT sent to Letta
6. Operator can hand back to AI by clearing flag

**Architecture Needs:**
- Mail channel with LLM mixin
- Letta agent creation on channel creation
- Message relay system
- Manual override flag
- Escalation tool in Letta

### Use Case 2: Company Bookkeeper Agent

**Scenario:** Shared agent (bookkeeper) that multiple users can interact with, maintaining company-wide memory.

**Requirements:**
1. Single `mail.channel` = "Company Bookkeeper"
2. Multiple users can join channel
3. Single Letta agent instance for all users
4. Shared memory blocks (company SOPs, procedures)
5. Permission-aware responses (user can only see their invoices)
6. Memory blocks updatable by authorized users

**Architecture Needs:**
- Group channels with LLM agents
- Shared Letta memory block management
- Permission system for tool execution
- User context in Letta calls

**Permission Challenge:**
- Currently: Agent runs with `llm.thread` user's permissions
- Needed: Agent runs with **current speaker's** permissions
- Solution: Pass `current_user_id` to Letta, execute Odoo tools with that user's context

## Letta Integration Requirements

### 1. Assistant Template Extension

**Current:** `llm.assistant` model
**Needed:** Extend for Letta-specific configuration

```python
class LLMAssistant(models.Model):
    _inherit = 'llm.assistant'

    # Letta fields
    is_letta_agent = fields.Boolean()
    letta_template_id = fields.Char()  # Template in Letta
    letta_memory_blocks = fields.One2many('llm.letta.memory_block', 'assistant_id')
    letta_tools = fields.Many2many('llm.tool')  # Tools available to agent
```

### 2. Memory Block Management

**New Model:** `llm.letta.memory_block`

```python
class LettaMemoryBlock(models.Model):
    _name = 'llm.letta.memory_block'

    name = fields.Char(required=True)
    label = fields.Char()  # Label in Letta
    content = fields.Text()
    shared = fields.Boolean()  # Shared across agent instances
    readonly_users = fields.Many2many('res.users', relation='readonly')
    write_users = fields.Many2many('res.users', relation='write')
```

**Use Cases:**
- Company SOPs (shared, editable by managers)
- User-specific memory (private)
- Project context (shared within team)

### 3. Tool Integration

**Current State:** Odoo internal tools work
**Needed:** Support external tools (MCP, Letta-native)

```python
class LLMTool(models.Model):
    _inherit = 'llm.tool'

    tool_type = fields.Selection([
        ('internal', 'Odoo Internal'),
        ('mcp', 'MCP Server'),
        ('letta', 'Letta Native'),
    ])

    # For Letta tools
    letta_tool_name = fields.Char()
```

## Implementation Roadmap

### Phase 1: Documentation & Current State (Priority 1)
**Deadline:** ASAP (before other work)

- [ ] Document current Letta integration
- [ ] Create example Letta agents (bookkeeper, accountant)
- [ ] Installation guide for Letta + Odoo LLM
- [ ] User guide: How to create and manage agents
- [ ] Tool configuration examples

**Deliverable:** Users can install, configure, and use Letta agents in Odoo 16/18

### Phase 2: Architecture Research (Priority 2)
**Deadline:** By end of week

**Tasks:**
- [ ] Review Odoo `mail.thread` implementation
- [ ] Review Odoo `mail.channel` implementation
- [ ] Analyze permission system in multi-user channels
- [ ] Research Letta SDK capabilities for shared memory
- [ ] Design LLM thread mixin vs model decision matrix

**Deliverable:** Technical design document with architecture options

### Phase 3: Letta Memory Block Management (Priority 3)

**Tasks:**
- [ ] Create `llm.letta.memory_block` model
- [ ] Implement memory block CRUD in Odoo
- [ ] Sync memory blocks with Letta agents
- [ ] Permission system for memory blocks
- [ ] UI for managing memory blocks

**Deliverable:** Shared memory blocks working

### Phase 4: Mail Channel Integration (Priority 4)

**Tasks:**
- [ ] Extend `mail.channel` with LLM fields
- [ ] Implement message relay to Letta
- [ ] Handle responses from Letta to channel
- [ ] Manual override flag and UI
- [ ] Escalation tool implementation

**Deliverable:** AI-powered discuss channels

### Phase 5: Live Chat Integration (Priority 5)

**Tasks:**
- [ ] Integrate with Odoo live chat module
- [ ] Auto-create Letta agents for new chats
- [ ] Escalation workflow
- [ ] Lead creation from chat
- [ ] Analytics and monitoring

**Deliverable:** Live chat with AI support

**Alternative:** External solution via Chatwoot + Letta + Odoo tools (lower priority)

### Phase 6: Multi-User Agent Permissions (Priority 6)

**Tasks:**
- [ ] Pass current user context to Letta
- [ ] Tool execution with user permissions
- [ ] Permission-aware responses
- [ ] Audit trail for agent actions

**Deliverable:** Secure multi-user agents

## Open Questions

### 1. Architecture Decision: Mixin vs Model

**Question:** Should we:
- A) Replace `llm.thread` model with mixin entirely?
- B) Keep both (mixin + model)?
- C) Keep model, add optional mixin mode?

**Considerations:**
- Backward compatibility with existing installations
- Data migration complexity
- Use case coverage

**Decision Needed:** Review with Alexey

### 2. Permission Model

**Question:** How should permissions work for multi-user agents?

**Options:**
- A) Agent always runs as specific "agent user"
- B) Agent runs as current speaking user
- C) Agent has elevated permissions, logs actions per user

**Decision Needed:** Security review

### 3. Letta vs Internal Agents

**Question:** Should we support both?

**Scenario:** Some users want simple agents (no Letta), others want advanced features.

**Proposal:** `llm.assistant.agent_type`:
- `simple` - Current Odoo-only implementation
- `letta` - Letta-powered with memory blocks

### 4. Mail Channel Linking

**Question:** Do we need `mail.channel` to link to business objects?

**Scenario:** "Project X Discussion" channel might need to link to `project.project` record.

**Current:** Mail channels are standalone
**Needed?:** Research if this is required for agents

## Success Criteria

By end of week, we should have:

1. ✅ **Documentation complete** - Anyone can install and use Letta agents in Odoo
2. ✅ **Example agents working** - Bookkeeper and accountant examples
3. ✅ **Architecture plan approved** - Clear roadmap for implementation
4. ✅ **Phase prioritization** - What to build first, what can wait

## Next Steps

1. **Immediate:** Finish Airastana documentation (different project)
2. **After Airastana:** Review this document, refine architecture plan
3. **Tomorrow:** Present plan to Alexey for review and adjustment
4. **This week:** Begin Phase 1 (documentation of current Letta integration)

## Technical Notes

### Current Letta Integration Status (18.0 branch)

**What works:**
- Create Letta agent through `llm.assistant`
- Chat with agent through `llm.thread`
- Odoo internal tools available to agent
- End-to-end conversation flow

**What's limited:**
- No external tool support (MCP, Letta-native)
- System instructions managed where? (clarify)
- No shared memory blocks
- Single-user only

**What's needed:**
- Clear documentation of setup process
- Example agent templates
- User-friendly configuration UI
- Tool management improvements

## References

- Meeting transcript: `/Users/saifulislam/Desktop/Meeting started 2025_10_21 09_29 AST - Notes by Gemini.txt`
- Current Letta integration: `llm_letta` module
- Mail architecture: `addons/mail/models/`
- Discuss module: `addons/mail/models/mail_channel.py`

## Appendix: Key Concepts Clarified

### mail.thread vs llm.thread

**mail.thread:**
- Mixin that adds messaging to any model
- Messages linked directly to records
- Example: `res.partner` → messages on contact

**llm.thread:**
- Separate model (record)
- Acts as intermediate layer
- Messages linked to thread, thread linked to object
- Allows multiple conversations per object

### mail.channel vs llm.thread

**Similarities:**
- Both are models (records)
- Both inherit `mail.thread`
- Both have messages linked to them
- Both enable threaded conversations

**Differences:**
- `mail.channel`: Odoo discuss channels, group conversations
- `llm.thread`: AI conversations, typically single user

**Proposed:** Make them work more similarly, allow LLM on channels

### Agent Template vs Agent Instance

**Template (llm.assistant):**
- Configuration blueprint
- Instructions, tools, memory blocks
- Reusable across multiple agents

**Instance (Letta agent):**
- Actual running agent
- Has accumulated memory
- Linked to specific channel/thread

**Analogy:** Class vs Object in programming
