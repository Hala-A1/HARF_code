# Instruction retrieval and preview

The administrator's **Test instruction retrieval** uses the same `instruction_bundle` selector as generation. It does not call the model. Use the same channel, content format and brief to compare results. A real batch uses all its briefs when selecting shared terminology, so a one-brief preview cannot represent additional briefs that were not supplied.

## Selection

- Channel permissions determine which instruction files are eligible. User/admin guides are excluded from writing prompts.
- B2B routes to website, paid search or messaging scope. A website component number selects that component's schema and excludes the other numbered components. Applicable shared tone, factual and legal rules remain included.
- B2C routes by content format or explicit stable ID, such as `B2C-SMS-001`. App and website formats inherit their Digital UX dependencies. Unrelated template families are excluded in both preview and generation.
- Applicable mandatory prose rules remain pinned. Glossary matching selects relevant bilingual rows and preserves core/restricted naming rules. Only labelled optional examples/reference sections are ranked with lexical BM25-style scoring. B2C archive catalogue tables are not sent alongside selected example bodies.
- No instructions are removed from the saved Markdown files by retrieval.

## Caching and token limits

`structure_retrieval.indexed_file` builds heading/line and terminology indexes on first use. Unchanged files reuse the in-memory index and bounded selection cache. A changed file signature or an administrator save invalidates the file's index. Restarting the backend clears these in-memory caches.

`GenerationContext` selects shared instructions once per generation request, including bulk worker threads and bilingual outputs. Component selections are reused for the same component within the request. This reduces file processing and repeated selection work.

Each **separate model call** still needs its applicable rules in its prompt. Sharing a server-side snapshot does not make a stateless model remember instructions across calls, nor guarantee provider-side prompt caching. The preview reports instruction characters, not exact tokens, cost, total prompt size or generation latency. Mandatory rules can remain sizeable; do not discard them merely to meet a smaller prompt budget. Security currently has one template, so selecting all its applicable rules is expected.

## Verification

`backend/test_retrieval_preview_parity.py` checks all 17 components, five B2C formats and stable template IDs, Security, preview/generation section parity, and warm-cache operation without another full-file read. `test_generation_context.py` verifies one shared selection across ten parallel components, request isolation, bilingual reuse, and updated rules on the next request.

Illustrative local measurement using fictional briefs (24 October 2026; characters, not tokens):

| Request | Full source characters | Selected characters | Reduction |
| --- | ---: | ---: | ---: |
| B2B website Component 3 | 1,997,854 | 239,610 | 88.0% |
| B2C SMS payment reminder | 217,639 | 59,705 | 72.6% |
| B2C email payment reminder | 217,639 | 65,404 | 69.9% |

Warm selector timings in that run were approximately 1–3 ms. These are observations for those briefs and saved revisions, not end-to-end generation guarantees.
