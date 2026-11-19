# Website Component Library — Fields and Character Limits

## Authority
Use the **Updated LLM Component Library** as the structural source of truth. It retains Components 1–10 from the original library and adds Components 11–17.

Character limits include spaces. Treat mandatory/optional status literally.

## Components

### Component 1 — Hero Image - Inner Page
- Image: mandatory, 1920 × 363
- Title: mandatory, max 20 characters
- Sub-title: mandatory, max 50 characters
- CTA: optional, one CTA

### Component 2 — Intro Copy
- Title: mandatory, max 65 characters
- Sub-title: mandatory, approximately 300 characters max; small paragraph
- CTA: optional, one CTA

### Component 3 — USPs
- Section heading: optional, max 40 characters
- Icon: mandatory
- Title: optional, max 20 characters
- Sub-title: optional, max 65 characters
- At least one textual content type must be present: title or description/sub-title, or both.

### Component 4 — USP Featured
- Icon: mandatory
- Title: mandatory, max 20 characters
- Sub-title: mandatory, max 65 characters

### Component 5 — Rate Plan Cards
- Plan Name: mandatory
- Price: mandatory
- Sticker: optional, max 25 characters
- Old/New Price: optional when discount applies
- USPs: mandatory; each has USP name + USP value
- Minimum 2 USPs
- Maximum 8 USPs displayed; additional USPs go under More Info
- Tooltip next to USP Name: optional
- More Info CTA: optional
- Contract Period: optional
- CTA: mandatory
  - `Buy Now` for an eCommerce journey
  - `Apply Now` for lead submission
- One or more rate-plan cards may be used depending on available plans.

### Component 6 — Collapse-Tree
- Featured Name: mandatory
  - Examples: Frequently Asked Questions, Important to Know, Required Documents
- Question/Answer: mandatory

### Component 7 — Cross-Selling Rotation Banner
- Image: mandatory
- Title: mandatory, max 20 characters
- Description: mandatory, max 180 characters
- CTA: optional
- One or more banners may be used.

### Component 8 — Unnamed in supplied library
The source does not provide a component name.
- Image: mandatory
- Title: mandatory, max 50 characters

Do not invent a component name. Refer to it as `Component 8 — name not specified in source` until an approved name is supplied.

### Component 9 — Image Cards 1
- Image: mandatory
- Title: mandatory, max 45 characters
- Description: mandatory, max 450 characters
- CTA: optional

### Component 10 — CTA Banner
- Title: mandatory, max 45 characters
- Description: mandatory, max 155 characters
- CTA: optional

### Component 11 — SMB Related Articles (4 Cards)
- Image: mandatory
- Title: mandatory, max 45 characters
- Description: mandatory, max 135 characters
- CTA: optional
- Source note: button is not visible except on hover.

### Component 12 — SMB Related Articles (2 Cards)
- Image: mandatory
- Title: mandatory, max 45 characters
- Description: mandatory, max 155 characters
- CTA: mandatory

### Component 13 — Benefits Component
- Icon: mandatory
- Title: mandatory, max 25 characters
- Description: mandatory, max 80 characters
- CTA: optional

### Component 14 — Smartphone Secondary Cards (Variation: Card with 4 line)
- Image: mandatory
- Heading: mandatory, max 25 characters
- Description: mandatory, max 90 characters
- Pre-Title: optional, max 40 characters
- Price: optional
- CTA: optional

### Component 15 — Smartphone Secondary Cards (Variation: Card with 2 line)
- Image: mandatory
- Heading: mandatory, max 25 characters
- Description: mandatory, max 120 characters
- Pre-Title: optional, max 40 characters
- Price: optional
- CTA: optional

### Component 16 — Cross Promo Banner (Two Column)
- Icon: mandatory
- Heading: mandatory, max 40 characters
- CTA: optional

### Component 17 — Featured Banner (Variation: Cross-sell banner with Media)
- Image: mandatory
- Heading: mandatory, max 40 characters
- Description: mandatory, max 215 characters
- CTA: optional


## Validation rules
- Count letters, numbers, spaces, symbols, and punctuation for every stated limit.
- Do not output a field over its limit.
- Do not invent a missing component name or missing field rule.
- Required visual assets (image/icon) should be represented as required inputs when the agent is responsible for validating completeness but is not generating the visual.
- Apply website tone and terminology rules separately; this schema defines structure, not the full writing voice.
