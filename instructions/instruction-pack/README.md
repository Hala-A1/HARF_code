# Instruction Library — File Roles and Routing Guide

> B2B migration note (14 October 2026): this directory now retains the previous source modules for provenance and backward compatibility. The active B2B library uses only `../channels/b2b/01_B2B_SYSTEM_INSTRUCTIONS.md`, `../channels/b2b/02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md`, and `../channels/b2b/03_B2B_USER_AND_ADMIN_GUIDE.md`. The previous loading examples below describe the former layout. All source content has been retained in the new pack and original-source archive. New channels receive a neutral system file, indexed template file and protected user/admin guide.

This folder converts the supplied etisalat source documents into modular Markdown instructions.

The modules in this folder supply B2B writing rules and the starter guides for new custom channels. B2C and Security use their own three-file packs under `../channels/`. Their generation rules and templates are isolated from B2B, and their administrator guide is excluded from generation prompts.

## Files
- `00_MASTER_INSTRUCTIONS.md` — orchestration, precedence, routing, factual safeguards, and validation.
- `01_BRAND_RULES.md` — standard brand naming, writing mechanics, CTA, UK English, currency, dates, punctuation, and formatting.
- `02_WEBSITE_CONTENT_INSTRUCTIONS.md` — website tone, perspective, structure, SEO/AEO/GEO, claim rules, inputs, output, and validation.
- `03_WEBSITE_COMPONENT_SCHEMA.md` — website component fields, mandatory/optional status, and character limits from the Updated Component Library.
- `04_GOOGLE_PAID_SEARCH_INSTRUCTIONS.md` — paid-search tone, pair logic, claims, hard limits, output format, and validation.
- `05_B2B_MESSAGING_EXAMPLES.md` — B2B before/after/Arabic examples and ready-to-send formatting patterns.

## Recommended loading
For website generation, load:
`Complete guide` + `01` + B2B messaging examples + `00` + `02` + `03`

For Google Paid Search, load:
`Complete guide` + `01` + B2B messaging examples + `00` + `04`

This avoids forcing website-specific component rules into ad generation while keeping shared brand rules consistent.
