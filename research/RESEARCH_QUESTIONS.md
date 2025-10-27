# Research Questions - LLM Thread to Mail Thread Refactoring

**Purpose:** Track specific questions that need research. Each question gets its own focused investigation in a subfolder.

**How to use:**
1. Add question below with `[ ]` checkbox
2. Claude researches and creates `/research/Q{number}/` folder with findings
3. Mark as `[x]` when answered with summary
4. Keep answers concise and focused

---

## Questions to Research

### Architecture & Patterns

- [x] **Q1:** Should llm.thread be a mixin (AbstractModel with _name) OR just extend mail.thread (AbstractModel with _inherit only)?
- [x] **Q2:** discuss.channel vs mail.channel - What's the difference? How does it work with our extension? Can we create DM with AI (non-user)?
- [x] **Q3:** AI as mail.guest vs AI as fake email author - Which approach? What are the use cases and trade-offs?
- [x] **Q4:** Shared agent in group channel (Company Bookkeeper) - How does it work? Does this change the mail.guest decision?
- [ ] **Q5:** How does Discuss app frontend work? (Components, models, bus events)
- [ ] **Q2:** How does Chatter work? (Integration with form views, message rendering)
- [ ] **Q3:** How do we add AI toggle button to Discuss UI?
- [ ] **Q4:** How do we add AI button to Chatter?
- [ ] **Q5:** How should message routing work? (Auto-reply vs @ai mention vs manual trigger)

### Letta Integration

- [ ] **Q6:** How do Letta memory blocks work?
- [ ] **Q7:** How to create Letta agent from Odoo assistant template?
- [ ] **Q8:** How to sync memory blocks between Odoo and Letta?
- [ ] **Q9:** How to handle Letta agent lifecycle (create/destroy)?
- [ ] **Q10:** How to pass Odoo context to Letta tools?

### Multi-User & Permissions

- [ ] **Q11:** How should permissions work for multi-user AI channels?
- [ ] **Q12:** Should AI run with current user permissions or fixed "AI user"?
- [ ] **Q13:** How to prevent AI from seeing restricted data?
- [ ] **Q14:** How to handle different users with different access levels in same channel?

### User Experience & Workflows

- [ ] **Q15:** What are the user workflows for AI in Discuss?
- [ ] **Q16:** What are the user workflows for AI in Chatter?
- [ ] **Q17:** How should AI escalation work in live chat?
- [ ] **Q18:** How should users enable/disable AI on a record?
- [ ] **Q19:** What happens when AI is disabled mid-conversation?

### Technical Implementation

- [ ] **Q20:** What's the minimal prototype to test the concept?
- [ ] **Q21:** How to migrate existing llm.thread records?
- [ ] **Q22:** How to handle backward compatibility?
- [ ] **Q23:** What are the performance implications at scale?
- [ ] **Q24:** How to prevent AI response loops?

### Edge Cases & Error Handling

- [ ] **Q25:** What happens if LLM provider is down?
- [ ] **Q26:** How to handle rate limits?
- [ ] **Q27:** What if user deletes AI message?
- [ ] **Q28:** How to handle very long conversations (context window)?

---

## Answered Questions

*(Questions move here when answered)*

---

## How to Add a Question

1. Add to appropriate section above with `[ ]` checkbox
2. Use format: `**Q{number}:** Clear, specific question`
3. Keep questions focused and answerable through research
4. Avoid "how to implement X" - focus on "how does X work"

---

## Research Structure

Each question gets a folder: `/research/Q{number}/`

Example structure:
```
/research/
  /Q1-discuss-frontend/
    findings.md          # Concise findings
    code-examples.py     # If needed
    screenshots/         # If helpful
  /Q2-chatter/
    findings.md
    ...
```

---

**Last Updated:** 2025-10-27
