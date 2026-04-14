# tool-fabric Registry Audit

> **Generated:** 2026-04-13  
> **Registry:** CARLOS-OS — multi-agent personal operating system  
> **Purpose:** Empirical data for §4 of the tool-fabric paper (formal framework validation)

**File:** `examples/carlos-os/.tool-fabric.yaml`

## Summary

| Metric | Count |
|--------|-------|
| Tools | 34 |
| Concepts | 21 |
| Patterns | 6 |
| MECE groups | 3 |
| Errors | 24 |
| Warnings | 19 |
| Info | 19 |
| **Total violations** | **62** |

## Violation Breakdown

| Code | Severity | Count |
|------|----------|-------|
| E002 | ERROR | 24 |
| I001 | INFO | 18 |
| I004 | INFO | 1 |
| W001 | WARNING | 16 |
| W006 | WARNING | 2 |
| W007 | WARNING | 1 |

## 🔴 Errors (24)

- **[E002]** Composition contract failure: 'github_search_issues' → 'github_create_issue': no shared fields between output ['total_count', 'issues'] and input ['body', 'labels', 'repo', 'title'].
- **[E002]** Composition contract failure: 'github_search_issues' → 'github_close_issue': no shared fields between output ['total_count', 'issues'] and input ['comment', 'repo', 'issue_number'].
- **[E002]** Composition contract failure: 'gmail_send' → 'gmail_create_draft': no shared fields between output ['message_id', 'thread_id'] and input ['to', 'subject', 'body'].
- **[E002]** Composition contract failure: 'bash_execute' → 'file_read': no shared fields between output ['stderr', 'exit_code', 'stdout'] and input ['path', 'limit', 'offset'].
- **[E002]** Composition contract failure: 'bash_execute' → 'file_write': no shared fields between output ['stderr', 'exit_code', 'stdout'] and input ['path', 'content'].
- **[E002]** Composition contract failure: 'bash_execute' → 'bash_execute': no shared fields between output ['stderr', 'exit_code', 'stdout'] and input ['command', 'timeout_ms', 'cwd'].
- **[E002]** Composition contract failure: 'github_create_pr' → 'slack_send_message': no shared fields between output ['pr_url', 'repo', 'pr_number'] and input ['channel_id', 'text', 'thread_ts'].
- **[E002]** Composition contract failure: 'web_search' → 'web_fetch': no shared fields between output ['query', 'results'] and input ['url', 'max_length'].
- **[E002]** Composition contract failure: 'file_read' → 'bash_execute': no shared fields between output ['path', 'content', 'lines'] and input ['command', 'timeout_ms', 'cwd'].
- **[E002]** Composition contract failure: 'file_write' → 'bash_execute': no shared fields between output ['path', 'bytes_written'] and input ['command', 'timeout_ms', 'cwd'].
- **[E002]** Composition contract failure: 'claude_invoke' → 'file_write': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['path', 'content'].
- **[E002]** Composition contract failure: 'claude_invoke' → 'slack_send_message': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['channel_id', 'text', 'thread_ts'].
- **[E002]** Composition contract failure: 'claude_invoke' → 'gmail_send': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['attachments', 'body', 'to', 'subject', 'cc'].
- **[E002]** Composition contract failure: 'calendar_create_event' → 'gmail_send': no shared fields between output ['event_url', 'event_id'] and input ['attachments', 'body', 'to', 'subject', 'cc'].
- **[E002]** Composition contract failure: 'calendar_find_slot' → 'calendar_create_event': no shared fields between output ['queried_range', 'available_slots'] and input ['end_datetime', 'description', 'start_datetime', 'title', 'attendees', 'calendar_id'].
- **[E002]** Composition contract failure: 'notion_update_budget' → 'slack_send_message': no shared fields between output ['page_id', 'last_edited'] and input ['channel_id', 'text', 'thread_ts'].
- **[E002]** Composition contract failure: 'notion_update_budget' → 'notion_query_database': no shared fields between output ['page_id', 'last_edited'] and input ['filter', 'database_id', 'sorts'].
- **[E002]** Composition contract failure: 'gmail_create_draft' → 'gmail_send': no shared fields between output ['draft_id'] and input ['attachments', 'body', 'to', 'subject', 'cc'].
- **[E002]** Composition contract failure: 'notion_query_database' → 'notion_update_budget': no shared fields between output ['pages', 'total'] and input ['page_id', 'properties'].
- **[E002]** Composition contract failure: 'python_execute' → 'file_write': no shared fields between output ['stderr', 'exit_code', 'stdout'] and input ['path', 'content'].
- **[E002]** Composition contract failure: 'gemini_invoke' → 'file_write': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['path', 'content'].
- **[E002]** Composition contract failure: 'gemini_invoke' → 'slack_send_message': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['channel_id', 'text', 'thread_ts'].
- **[E002]** Composition contract failure: 'gpt_invoke' → 'file_write': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['path', 'content'].
- **[E002]** Composition contract failure: 'gpt_invoke' → 'slack_send_message': no shared fields between output ['response', 'usage_tokens', 'model'] and input ['channel_id', 'text', 'thread_ts'].

## 🟡 Warnings (19)

- **[W001]** Orphan tool: 'github_create_issue' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'bash_execute' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'file_read' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'github_assign_issue' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'github_add_label' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'github_link_pr' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'github_close_issue' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'linear_add_to_cycle' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'linear_search_issues' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'slack_add_reaction' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'slack_send_message_thread' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'gmail_add_label' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'gmail_create_draft' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'python_execute' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'gemini_invoke' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W001]** Orphan tool: 'gpt_invoke' is not referenced in any pattern. Consider adding it to a pattern or documenting why it is standalone.
- **[W006]** Vocabulary inconsistency in MECE group 'create a project tracking issue': mixed synonyms ['issue', 'task'] detected. Per-tool usage: 'github_create_issue'→['issue', 'task'], 'linear_create_issue'→['issue']. Use the concept DAG's canonical term throughout.
- **[W006]** Vocabulary inconsistency in MECE group 'send a message to a person or team': mixed synonyms ['email', 'message'] detected. Per-tool usage: 'gmail_send'→['email', 'message'], 'slack_send_message'→['email', 'message']. Use the concept DAG's canonical term throughout.
- **[W007]** Minimality violation: 'gemini_invoke' and 'gpt_invoke' are declared as alternatives and have identical input/output shapes (input: ['max_tokens', 'model', 'prompt'], output: ['model', 'response', 'usage_tokens']). Consider merging into one tool or adding a distinguishing field.

## 🔵 Info (19)

- **[I001]** 'github_assign_issue': description has 9 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'github_add_label': description has 12 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'github_link_pr': description has 10 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'github_close_issue': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'github_request_review': description has 10 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'linear_assign_issue': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'linear_set_priority': description has 9 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'linear_add_to_cycle': description has 9 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'linear_search_issues': description has 9 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'slack_add_reaction': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'slack_send_message_thread': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'gmail_add_label': description has 9 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'gmail_create_draft': description has 7 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'notion_query_database': description has 10 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'calendar_invite_attendees': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'docs_search': description has 7 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'gemini_invoke': description has 8 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I001]** 'gpt_invoke': description has 6 words (target: 20-60). Short descriptions reduce selection accuracy.
- **[I004]** Completeness gap: concept 'github.issue' is defined in the DAG but no tool declares it in concepts_required. Add a tool that requires it, or remove the concept.

