# Q1: Mixin vs Extension - Should llm.thread have _name or not?

**Question:** Should llm.thread be a mixin (with `_name`) OR just extend mail.thread (only `_inherit`)?

---

## Short Answer

**Remove `_name`, just use `_inherit = 'mail.thread'`** ✅

**Why:** This is the standard Odoo pattern (SMS and Rating modules do this).

---

## Two Options Explained

### Option A: Mixin with _name (Current?)

```python
class LLMThreadMixin(models.AbstractModel):
    _name = 'llm.thread.mixin'
    _description = 'LLM Thread Mixin'

    llm_enabled = fields.Boolean()
    # ... fields
```

**Problem:** Models must explicitly inherit it:
```python
class DiscussChannel(models.Model):
    _inherit = ['discuss.channel', 'llm.thread.mixin']  # Manual inheritance needed
```

**This means:**
- ❌ Every model needs to explicitly add 'llm.thread.mixin'
- ❌ Not automatic
- ❌ Easy to forget
- ❌ Not how Odoo core does it

---

### Option B: Direct Extension (RECOMMENDED) ✅

```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    # NO _name!

    llm_enabled = fields.Boolean(default=False)
    # ... fields
```

**Benefit:** Automatically works on ALL models that inherit mail.thread:
```python
# discuss.channel - already inherits mail.thread, so it gets llm_enabled automatically
# project.task - already inherits mail.thread, so it gets llm_enabled automatically
# sale.order - already inherits mail.thread, so it gets llm_enabled automatically
```

**This means:**
- ✅ Automatic everywhere
- ✅ Just enable with flag: `record.llm_enabled = True`
- ✅ Standard Odoo pattern
- ✅ Less code

---

## Evidence from Odoo Core

### SMS Module Does This:

```python
# File: addons/sms/models/mail_thread.py
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    # NO _name!

    message_has_sms_error = fields.Boolean(...)

    def message_post(self, **kwargs):
        # Override message_post
        ...
```

**Result:** ALL models get SMS capability automatically.

### Rating Module Does This:

```python
# File: addons/rating/models/mail_thread.py
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    # NO _name!

    rating_ids = fields.One2many(...)

    def message_post(self, **kwargs):
        # Override for ratings
        ...
```

**Result:** ALL models get rating capability automatically.

---

## Your Concern: "Can't use it directly on all models"

**Answer:** That's actually the GOAL! We WANT it on all models automatically.

**Why?**
- User can enable AI on ANY record: tasks, orders, partners, etc.
- Just set `llm_enabled = True` where needed
- No manual inheritance management
- Works everywhere consistently

**Example:**
```python
# Enable AI on a task
task.llm_enabled = True
task.llm_provider_id = provider.id
# Now task has AI!

# Enable AI on a channel
channel.llm_enabled = True
channel.llm_provider_id = provider.id
# Now channel has AI!

# Leave AI disabled on other records
# Fields exist but llm_enabled=False, so they're ignored
```

---

## Your Second Point: "Flag to turn on llm mode"

**That's exactly right!** ✅

```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    llm_enabled = fields.Boolean(
        string="AI Enabled",
        default=False,  # OFF by default
        help="Enable AI responses on this record"
    )
```

**This is the "flag" you mentioned!**

When `llm_enabled=False` (default):
- Fields exist but are ignored
- No AI processing happens
- No performance impact

When `llm_enabled=True`:
- AI kicks in
- Can generate responses
- Context provided to AI

---

## Current llm.thread Model

**What happens to it?**

Option 1: Delete it completely (breaking change)
Option 2: Keep as wrapper pointing to discuss.channel (backward compatible)

**Recommendation:** Option 2 for smooth migration

```python
class LLMThread(models.Model):
    _name = 'llm.thread'
    _inherit = ['discuss.channel']  # Now inherits from channel!
    _description = 'DEPRECATED: Use discuss.channel with llm_enabled=True'

    def create(self, vals_list):
        # Show warning
        _logger.warning("llm.thread is deprecated, use discuss.channel")
        # Convert to channel creation
        for vals in vals_list:
            vals['llm_enabled'] = True
        return super().create(vals_list)
```

---

## Summary

**Question:** Mixin with _name OR just extend mail.thread?

**Answer:** Just extend mail.thread (no _name) ✅

**Pattern:**
```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'  # Only _inherit, no _name
    llm_enabled = fields.Boolean(default=False)
    # ... rest of fields and methods
```

**Benefits:**
- ✅ Automatic on all models
- ✅ Standard Odoo pattern
- ✅ Simple flag-based activation
- ✅ No manual inheritance needed
- ✅ Consistent everywhere

**This is how SMS and Rating work, and it works perfectly.**
