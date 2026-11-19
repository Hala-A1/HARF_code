# B2C — Indexed Channel and Template Instructions

Pack ID: B2C-CX | Document ID: B2C-TEMPLATES | Version: 1.1 | Updated: 21 October 2026

Status: active B2C template instructions. Template rules and dependencies are defined below; reference examples illustrate their application.

Scope: channel-specific behaviour, field structures, limits and source examples. Shared writing rules are defined once in System Instructions (01_B2C_SYSTEM_INSTRUCTIONS.md).

## Index conventions

IDs are permanent, human-readable keys. Aliases help future matching but are not executable routing. Parent entries contain the channel's common schema; variants inherit that parent and add only their differences. A future retrieval method would need the system file, selected parent, variant and any referenced schema. The active loader keeps all template rules and dependencies together; optional examples are ranked by the existing retrieval method.

```text
status: source_backed means supported by the supplied B2C sources, not legally approved for publication. Standardised field layouts are consolidation choices derived from those sources, not a claim that every optional field is mandatory in every source. required_inputs identifies drafting dependencies; information that does not apply should be omitted, not invented.
```

| Stable ID | Channel / variant | Search aliases | Parent / dependency |
| --- | --- | --- | --- |
| [B2C-SMS-001](#b2c-sms-001) | SMS | text message, SMS, رسالة نصية | System |
| [B2C-SMS-002](#b2c-sms-002) | SMS action journey | activation, installation, welcome, تفعيل | SMS-001 |
| [B2C-SMS-003](#b2c-sms-003) | SMS service or transaction update | balance, payment, transfer, OTP, roaming, رصيد، تحويل | SMS-001 |
| [B2C-SMS-004](#b2c-sms-004) | SMS disruption notice | crisis, outage, service restriction, انقطاع | SMS-001 |
| [B2C-EMAIL-001](#b2c-email-001) | Email | email, e-mail, بريد إلكتروني | System |
| [B2C-EMAIL-002](#b2c-email-002) | Email welcome / activation journey | onboarding, first bill, welcome, ترحيب | EMAIL-001 |
| [B2C-EMAIL-003](#b2c-email-003) | Email payment / escalation journey | bill, reminder, overdue, suspension, فاتورة | EMAIL-001 |
| [B2C-EMAIL-004](#b2c-email-004) | Email crisis / service recovery | disruption, apology, restrictions, اعتذار | EMAIL-001 |
| [B2C-UX-001](#b2c-ux-001) | Digital UX journeys | functional journey, app, web, SAS, UX, تجربة المستخدم | System |
| [B2C-WEB-001](#b2c-web-001) | Website content | web, landing page, website, موقع | System + UX-001 for functional journeys |
| [B2C-APP-001](#b2c-app-001) | App copy and screen-specific fields | app, in-app, banner, تطبيق | System + UX-001 |
| [B2C-APP-002](#b2c-app-002) | App action, support or small moment | Autopay, support, home move, مساعدة | APP-001 |
| [B2C-PUSH-001](#b2c-push-001) | Push notification | push, notification, إشعار | System; own PUSH-001 field schema |
| [B2C-PUSH-002](#b2c-push-002) | Push welcome / expiry journey | welcome gift, expiry, renewal, هدية | PUSH-001 |
| [B2C-PUSH-003](#b2c-push-003) | Push disruption / technical issue | outage, technical issue, خلل | PUSH-001 |

The shortened parent labels above refer to the full B2C- IDs. Channel means a delivery format here; B2C is the application workspace. SMS and email do not represent new application workspaces.

<a id="b2c-sms-001"></a>

## B2C-SMS-001 — SMS

```text
template_id: B2C-SMS-001
parent_id: null
aliases: [SMS, text message, رسالة نصية]
status: source_backed
source_refs: [CX-FINAL pp.26-28, STYLE pp.8-9, BANK SMS_Final, BANK Most Sent SMS_Final]
required_inputs: [message purpose, relevant facts, next action, language]
fields: [message]
limit_type: editorial_target
target: around 150 characters; generally remain under 320 characters when essential information requires a longer message
```

Aim for around 150 characters per SMS. Longer messages may be used when necessary to include essential information, but should generally remain under 320 characters. These are editorial guidelines, not technical SMS character limits. Lead with customer value or the essential update. Keep a quick, clear pace. Fragments are acceptable when unambiguous. Use urgency only for a real, verified deadline. If the message is split, each part must make sense by itself. Real plan names, links and other dynamic values affect length.

Use universally understood wording; do not use “unlimited” as a replacement for “non-stop” unless the actual service claim supports it. Exclamation marks may be used sparingly in SMS. For a youth brief, use no more than one appropriate emoji; no emoji for a formal or sensitive communication. Minimise dash spacing where space is tight without losing readability. Use an approved short link if needed; the source's shortener suggestion does not authorise inventing one.

Required approved opt-out or other SMS disclosure remains part of the message and its count. If its wording is missing, request it. A personalised greeting is optional and should earn its space.

Output shape: one ready-to-send message per requested SMS, without “Body:” or commentary inside the message. Put any segmentation labels, counts or unresolved requirements outside customer copy when requested.

<a id="b2c-sms-002"></a>

### B2C-SMS-002 — Action journey

Parent: B2C-SMS-001. Sources: CX-FINAL pp.71–73.

Required inputs: actual journey step; completed action; next action; relevant booking/product facts.

| Confirmed step | Message focus |
| --- | --- |
| Order placed | Acknowledge order; tell the customer how booking details will arrive |
| Appointment booked | Confirm the actual date/window; include rescheduling route if available |
| Technician on the way | State the verified update and useful next step |
| Included benefit not activated | Explain the verified included benefit and activation action |

Generate the requested step or a clearly separated sequence, not an undifferentiated paragraph containing every stage.

<a id="b2c-sms-003"></a>

### B2C-SMS-003 — Service and transaction update

Parent: B2C-SMS-001. Sources: BANK SMS_Final and Most Sent SMS_Final.

Required inputs depend on the event: service/account state; relevant amount/date; masked identifier where appropriate; transaction/reference token; customer action or confirmation.

Choose the relevant pattern: offer expiry → effective date/new charge/retained benefits; low balance or ineligible add-on → reason/action; processed payment → essential confirmation/details; reward earned → verified reward/balance; money transfer → correct pending or received state; OTP → exact token and approved security warning; roaming arrival → approved country-specific option and rate. Never combine “sent” and “received” states without evidence. Keep reference numbers where required. Do not copy an example support number, USSD code or offer rate unless it is approved for this request.

<a id="b2c-sms-004"></a>

### B2C-SMS-004 — Disruption notice

Parent: B2C-SMS-001. Source: CX-FINAL pp.95–97.

Required inputs: confirmed affected service/location; timing if known; unaffected capability if relevant; approved information/support link.

Prioritise the key impact, useful unaffected service and next action. Link to further detail where available instead of compressing every crisis fact into SMS. Do not use promotional embellishment.

<a id="b2c-email-001"></a>

## B2C-EMAIL-001 — Email

```text
template_id: B2C-EMAIL-001
parent_id: null
aliases: [email, e-mail, بريد إلكتروني]
status: source_backed
source_refs: [CX-FINAL pp.23-25, BANK Email_Final]
required_inputs: [purpose, relevant facts, next action, language]
fields: [subject, optional header, greeting where appropriate, body, CTA where needed, sign-off where appropriate, approved footer where required]
limits: no universal numeric email limit supplied
```

Sound like a direct, personal conversation. Address the customer with “you” and “your”; personalise when appropriate. Respect the inbox: include what is needed at this moment, not every product detail. Clarity comes before creativity. Each CTA expresses one action.

A subject identifies the important update; an optional header supports it instead of repeating it without purpose. Use short body paragraphs or a meaningful list. Include an account reference only when needed; do not copy the workbook's erroneous date-like account-number placeholder as a real identifier. Use approved opt-out/footer wording where required. Do not invent a numeric subject or body cap from another channel.

Output shape: clearly separated Subject, optional Header, then the ready-to-send email with greeting/body/CTA/sign-off as appropriate. Arabic labels must be Arabic. Required footer text belongs with the email; validation commentary does not.

<a id="b2c-email-002"></a>

### B2C-EMAIL-002 — Welcome and activation journey

Parent: B2C-EMAIL-001. Sources: CX-FINAL pp.74–75; BANK Email_Final rows 3, 6–7, 9.

Required inputs: actual activation state; product and included benefits; first-bill facts if relevant; action link.

For activation pending, focus on the one remaining activation step. After activation, acknowledge completion and explain relevant benefits; do not ask for activation again. For first-bill education, separate what to expect from subsequent reminder messages; preserve supplied billing calculation/period explanations. Welcome, device-protection and parental-control emails should explain the verified coverage/service and usable next step, not add unsupported promises.

<a id="b2c-email-003"></a>

### B2C-EMAIL-003 — Payment and escalation journey

Parent: B2C-EMAIL-001. Sources: CX-FINAL pp.76–79, 102–104; BANK Email_Final rows 4–5, 8.

Required inputs: verified balance, due date, current payment/service state, approved consequence and recovery route.

| Stage | Subject/body emphasis |
| --- | --- |
| Before due date | Helpful reminder; amount/date; payment or approved Autopay option |
| Due today | Clear same-day action and relevant reason to act |
| Overdue | Firm, factual notice; approved consequences and payment route |
| Confirmed approaching restriction | Exact approved deadline and affected service; urgency without threats |
| Restriction applied | Confirm what has actually stopped and how to restore it |
| Final sensitive escalation | Make the verified serious outcome clear; explain recovery without blame |

The source's 24-hour, five-hour and 55-day examples are not default policy. A promise-to-pay breach requires the actual agreed date and state. Include “already paid” handling only when operationally appropriate. Keep different stages as separate emails.

<a id="b2c-email-004"></a>

### B2C-EMAIL-004 — Crisis and service recovery

Parent: B2C-EMAIL-001. Sources: CX-FINAL pp.92–96; BANK Email_Final row 10.

Required inputs: confirmed issue/impact; known timing; practical alternatives; support route; verified completed corrective actions if any.

Use a factual subject, concise impact header where helpful, short explanation, useful bullet list, next action and support CTA. State what still works when that reduces uncertainty. A personal apology may be signed by a real responsible agent; never invent that identity or compensation. External-crisis copy should explain impact and options without claiming control over third-party restrictions.

<a id="b2c-ux-001"></a>

## B2C-UX-001 — Digital UX Journey Writing Guidelines

```text
template_id: B2C-UX-001
parent_id: null
aliases: [digital UX, functional journey, app, web, SAS, digital touchpoint, تجربة المستخدم]
status: source_backed
source_refs: [Writing Guidelines for Digital UX Journeys.docx, sections 1–4]
required_inputs: [screen or component, journey stage, customer task, verified facts, supported fields, brief or design limits, language]
```

Scope: shared guidance for functional journeys across app, web, SAS and other digital touchpoints. B2C-APP-001 and B2C-WEB-001 reference this section where applicable and retain their channel-specific requirements. Push notification field limits are defined separately in B2C-PUSH-001.

### 1. UX Copy Structure

UX copy should be clear, concise, and tailored to the screen’s purpose. Depending on the user journey, the following elements may be required:

| Element | Guidelines |
| --- | --- |
| Headline | Short, clear, and focused on the main message, action, or benefit. |
| Subhead / Supporting text | Provides relevant context, explains the next step, or highlights important information without repeating the headline. |
| CTA (Call to Action) | Short, action-oriented, and clearly communicates what happens next. |
| Microcopy | Helpful, concise guidance for form fields, tooltips, errors, confirmations, and other interface elements. |

Note: Not every screen requires all elements. The copy structure should be determined by the specific screen, component, or customer journey, regardless of the digital channel or touchpoint. Review or generate only the elements requested or relevant to the context, without automatically adding additional fields.

### 2. etisalat UX Writing Principles

Clear and simple

Prioritise clarity over creativity.

Use everyday language and avoid technical jargon.

Make messages easy to understand at first glance.

Concise and purposeful

Keep sentences short and easy to scan.

Remove unnecessary words and repetitive information.

Ensure every word adds value to the experience.

Human and customer-focused

Use a natural, friendly, and professional tone.

Address customers directly using “you” and “your” where appropriate.

Focus on customer benefits rather than product features alone.

Avoid robotic, overly formal, or excessively promotional language.

Context-aware

Onboarding: Welcoming and encouraging.

Plan selection: Informative and benefit-focused.

Checkout and payment: Clear, transparent, and reassuring.

Error messages: Helpful, calm, and solution-oriented.

Success messages: Positive, concise, and reassuring.

Account management: Direct, informative, and action-focused.

Consistent and accurate

Use approved etisalat terminology and product names (e.g., Home Plans, postpaid).

Apply sentence case to headlines, supporting text, and CTAs.

Maintain consistent terminology across screens and journeys.

Respect specified character limits.

Never invent product benefits, prices, eligibility conditions, or offers.

### 3. UX Copy Examples: Avoid vs. Preferred

The following examples illustrate the preferred etisalat writing style.

| Screen type | Avoid | Preferred |
| --- | --- | --- |
| Onboarding | Welcome to our amazing digital experience! | Let’s get started |
| Plan selection | Discover our incredible range of exciting plans! | Find the right plan for you |
| Payment error | Your transaction has encountered an unexpected error. | Payment unsuccessful. Please try again. |
| Success message | Congratulations! Your request has been successfully processed! | Your request has been processed |
| Account management | Kindly proceed to modify your account information. | Update your account details |
| CTA | Click here to proceed | Continue |
| Empty state | Unfortunately, there is no information available. | Nothing to show yet |

Key principle: UX copy should guide customers naturally, without unnecessary explanations, exaggerated language, or repetition. Any suggested improvements must preserve the original meaning, intent, and stage of the user journey.

### 4. English & Arabic Guidelines

Ensure English and Arabic communicate the same meaning and intent.

Prioritise natural, locally relevant Arabic over literal translations.

Maintain etisalat’s friendly, clear, and professional tone in both languages.

Use approved Arabic terminology for products, services, and actions.

Consider text length and right-to-left layouts when reviewing Arabic UX copy.

Keep CTAs concise and consistent across both languages.

<a id="b2c-web-001"></a>

## B2C-WEB-001 — Website content

```text
template_id: B2C-WEB-001
parent_id: null
aliases: [website, landing page, web content, موقع]
status: source_backed
source_refs: [CX-FINAL pp.29-33]
guideline_dependency: B2C-UX-001 for functional website journeys
required_inputs: [page goal, verified value proposition, relevant facts, desired next action]
fields: [headline, supporting copy as needed, CTA as needed]
limits: use supplied page constraints; no numbered component schema in these B2C sources
```

Use the most inspiring and confident expression of the B2C voice. Frontload value and vision; make an impact quickly. Build a short narrative instead of a long introduction. Purposeful repetition across a website can build familiarity. Put supporting detail in the right place without hiding a condition that changes a headline claim.

For functional website screens and journeys, apply B2C-UX-001. Use only the elements supported by the screen or component; retain the website-specific requirements above for relevant marketing content.

Source illustration: “Get gold from old” is explained by “Trade in your old tech, and get credit towards your dream device.” A creative line needs supporting clarity. The source's “Half the price. Half a year.” must not replace a variable “up to 50%” claim unless uniform eligibility and saving are confirmed.

Output shape: clearly named page/content block, headline, supporting text and relevant CTA. Use the brief's approved component schema if supplied; otherwise request it for a numbered component. Do not invent B2C Component 1–17 requirements or import the B2B prohibition on “you/your”.

<a id="b2c-app-001"></a>

## B2C-APP-001 — App copy and screen-specific fields

```text
template_id: B2C-APP-001
parent_id: null
aliases: [app, in-app, application copy, تطبيق]
status: source_backed
source_refs: [CX-FINAL pp.34-36, STYLE p.5, Writing Guidelines for Digital UX Journeys.docx]
guideline_dependency: B2C-UX-001
required_inputs: [screen or journey state, user goal, relevant facts, destination action]
fields: determined by the screen or component; headline, supporting text, CTA and microcopy only where required
limits: follow character limits supplied in the brief or design; no universal four-field app schema
```

Use only the copy elements required by the screen or component. Follow any character limits specified in the brief or design. Do not introduce any additional fields or content that the screen does not require. Apply B2C-UX-001. Lead with clarity, human support and empathy. Do not force humour or elaborate creativity. Walk the user journey through with a teammate before release.

Dates can use an abbreviated month, such as 31 Aug, where suitable. A youth brief may use one appropriate emoji at a time. Other source examples do not grant a blanket emoji or exclamation permission. Check count and visual fit for both languages.

Output shape: output only the copy elements required by the screen or component, using the field labels provided in the brief or the design. Do not add fields that are not supported by the interface. Render field labels in the requested language and provide character counts separately when requested.

<a id="b2c-app-002"></a>

### B2C-APP-002 — Action, support and small moments

Parent: B2C-APP-001. Sources: CX-FINAL pp.35–36, 81–88.

Required inputs: actual screen, action and supported fields.

Use the customer's task language (“moving” rather than “relocating”, “account” rather than an unnecessary service label). For Autopay, connect a verified convenience benefit with the clear action “Turn on Autopay”. For a section discovery label, the source illustrates “New for you”. For support entry, “How can we help?” is more human than “Type your issues here”. These are pattern examples; do not force a promotional title into a task-critical screen.

<a id="b2c-push-001"></a>

## B2C-PUSH-001 — Push notification

```text
template_id: B2C-PUSH-001
parent_id: null
schema_dependency: self-contained B2C-PUSH-001 field schema
aliases: [push, push notification, notification, إشعار]
status: source_backed
source_refs: [CX-FINAL pp.34,99,122, BANK Push Notification_Final]
required_inputs: [trigger, relevant fact or benefit, action, supported destination fields]
fields: [title, short description, long description where supported, CTA where supported]
character_maxima:
  title: 25
  short_description: 90
  long_description: 250
  CTA: 15
```

Lead with the main message in the title. The title must communicate the essential information independently, without relying on the short or long description. Use the short description for supporting details or the next step, and the long description for additional context. Avoid repeating the title unnecessarily. Do not put a fact needed to correct a misleading short field only in the long description. Make the CTA match the destination. Use an approved short link only if the delivery surface needs one. Dates may use an abbreviated month, such as 31 Aug, where suitable. A youth brief may use one appropriate emoji at a time; this is not a blanket emoji or exclamation permission. Check count and visual fit in both languages.

Output shape: title and the supporting notification or destination fields that the surface actually supports, each clearly separated. Do not invent unsupported fields. Apply the character maxima above to each included field, including spaces, punctuation and inserted dynamic values. Some historical examples exceed the limits; rewrite and recount instead of copying their lengths.

<a id="b2c-push-002"></a>

### B2C-PUSH-002 — Welcome, expiry and renewal

Parent: B2C-PUSH-001. Source: BANK Push Notification_Final rows 2–6.

Required inputs: verified gift/benefit; remaining validity or charge/renewal date; action or management destination.

For a welcome gift, explain the real choice/benefit and how to claim. Later reminders can increase urgency only against the actual expiry. For automatic renewal, clearly state the confirmed renewal or charge and whether action is needed. Do not imply that a customer must act to keep an automatic benefit unless that is true.

<a id="b2c-push-003"></a>

### B2C-PUSH-003 — Disruption or technical issue

Parent: B2C-PUSH-001. Sources: CX-FINAL p.99; BANK Push Notification_Final row 7.

Required inputs: confirmed issue, effect, practical action and any approved remedy.

Put core impact in the short fields; add practical steps in the long field if available. The sample free-technician remedy is usable only when confirmed for the actual customer. Do not invent a booking commitment.

## Formats without a supplied B2C schema

WhatsApp, social posts, Google Paid Search, numbered website components and other formats have no dedicated complete B2C schema in the reviewed sources. Ask for the approved format/limits if requested. Do not convert a B2B source into a B2C instruction silently. Add new approved formats using the administrator procedure, with a new stable ID; this is a future documentation change, not automatic app support.

## Source example archive

The following 47 populated workbook rows are retained once, with permanent example IDs. The examples incorporate the reviewed wording and official app naming updates. Blank cells/rows are not invented. English “Before” is comparison material, never a model to follow. “After” and Arabic examples illustrate structure and tone but are not automatically valid for a new brief: recount, proofread, localise labels and apply the system’s source-conflict controls. Do not reuse their historical commercial facts. Email_Final’s third column is labelled “AFTER” in the original workbook but contains Arabic.

One workbook row may contain several journey emails. All text within that row is preserved together. Code fences protect placeholders and line breaks; they are an archival presentation, not an instruction to put generated customer copy in code fences.

### BANK — SMS_Final

Channel dependency: B2C-SMS-001. Populated examples: 11.

| Example ID | Source row | English-after preview |
| --- | --- | --- |
| [B2C-EX-SMS-R002](#b2c-ex-sms-r002) | 2 | Hello <Name>, your $offer_name$ on your $service_name$ expires on $date$. Your new monthly charges will be AED… |
| [B2C-EX-SMS-R003](#b2c-ex-sms-r003) | 3 | You've got credit in your account <AccountNumber>. Want it refunded? Claim here: <Link> |
| [B2C-EX-SMS-R004](#b2c-ex-sms-r004) | 4 | Hello <Name>, welcome to $Neo Smart Home_Add-on_Plan name$. Your 24-month plan is now active. Want to check yo… |
| [B2C-EX-SMS-R005](#b2c-ex-sms-r005) | 5 | Important: Your "Promise to Pay" deadline has passed, but we haven't received your payment. Your services for… |
| [B2C-EX-SMS-R006](#b2c-ex-sms-r006) | 6 | Hello $Name$. As requested, we've cancelled your account ($Number$). We'll send you a confirmation email soon.… |
| [B2C-EX-SMS-R007](#b2c-ex-sms-r007) | 7 | Good news – we've fixed the issue on your account <Acc>. Read the full report here <Link> |
| [B2C-EX-SMS-R008](#b2c-ex-sms-r008) | 8 | Hello there, your bill of AED $amount_due$ for account $account_number$ is due on $due_date$. Pay now in a few… |
| [B2C-EX-SMS-R009](#b2c-ex-sms-r009) | 9 | Hello there, your bill of AED $amount_due$ for account $account_number$ is due today. Please pay now in the et… |
| [B2C-EX-SMS-R010](#b2c-ex-sms-r010) | 10 | Important: your bill of AED $amount_due$ for account $account_number$ is overdue. Pay now in the etisalat UAE… |
| [B2C-EX-SMS-R011](#b2c-ex-sms-r011) | 11 | Important: your bill of AED $amount_due$ for account $account_number$ is still outstanding. Not paying may aff… |
| [B2C-EX-SMS-R012](#b2c-ex-sms-r012) | 12 | You've subscribed to Special Roaming Daily Data Offer for AED 17.50 (excl. VAT)! Enjoy 500MB for 24 hours, whi… |

<a id="b2c-ex-sms-r002"></a>

#### B2C-EX-SMS-R002

Source: BANK / SMS_Final / row 2. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, 
Your $offer_name$ on your $service_name$ will expire on $date$. Your monthly charges will be AED $charges$ and you will continue to enjoy $benefits_list$.

Thank you for choosing etisalat.
```

**English after — source example**

```text
Hello <Name>, your $offer_name$ on your $service_name$ expires on $date$. Your new monthly charges will be AED $charges$, and you'll still have $benefits_list$. Learn more in the etisalat UAE app: <App link>
```

**Arabic — source example**

```text
مرحباً <Name>، ستنتهي صلاحية عرض $offer_name$ على خدمة $service_name$ بتاريخ $date$. وسيتم احتساب رسوم شهرية بقيمة $charges$ درهم، مع استمرار المزايا نفسها: $benefits_list$. اعرف أكثر عبر تطبيق etisalat UAE: <App link>
```

<a id="b2c-ex-sms-r003"></a>

#### B2C-EX-SMS-R003

Source: BANK / SMS_Final / row 3. Parent: B2C-SMS-001.

**English before — comparison only**

```text
You’re eligible for a refund of an Excess balance in your account <AccountNumber>. Please confirm your information to initiate the refund process at <Link>.
```

**English after — source example**

```text
You've got credit in your account <AccountNumber>. Want it refunded? Claim here: <Link>
```

**Arabic — source example**

```text
يتوفَّر لديك رصيد في حساب <AccountNumber>. هل ترغب في استرداده؟ قدّم طلبك هنا: <Link>
```

<a id="b2c-ex-sms-r004"></a>

#### B2C-EX-SMS-R004

Source: BANK / SMS_Final / row 4. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear <Customer>,

Welcome to the $Neo Smart Home_Add-on_Plan name$! Your plan is now active with a 24-month contract. 

Thank you for choosing etisalat.
```

**English after — source example**

```text
Hello <Name>, welcome to $Neo Smart Home_Add-on_Plan name$. Your 24-month plan is now active. Want to check your speed, manage your bills, and more? It's all in the etisalat UAE app.

Thanks for choosing etisalat, and enjoy your world of more.
```

**Arabic — source example**

```text
مرحباً <Name>، أهلًا بك في $Neo Smart Home_Add-on_Plan name$. تم تفعيل باقتك لمدة 24 شهراً. يمكنك التحقّق من السرعة، إدارة الفواتير، وأكثر عبر تطبيق واحد.
مع اتصالات، دايماً في أكثر. شكراً لاختيارك اتصالات.
```

<a id="b2c-ex-sms-r005"></a>

#### B2C-EX-SMS-R005

Source: BANK / SMS_Final / row 5. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, 
Your "Promise to Pay" commitment deadline has passed, and the payment has not been received.

We inform you that all services have been temporarily suspended for account $account_number$ due to an outstanding balance of AED $amount_due$. To restore your services, please make the payment by visiting etisalat.ae/quickpay. 

Thank you for choosing etisalat.
```

**English after — source example**

```text
Important: Your "Promise to Pay" deadline has passed, but we haven't received your payment. 

Your services for account $account_number$ have now been temporarily suspended, because of your outstanding balance of AED $amount_due$.

Pay now to reconnect and enjoy etisalat: etisalat.ae/quickpay. 

```

**Arabic — source example**

```text
تنبيه هام: لقد انتهت مهلة الدفع (Promise to Pay) دون استلام المبلغ.
تم إيقاف خدمات الحساب $account_number$ مؤقتاً، بسبب الرصيد المستحق بقيمة $amount_due$ درهم.
ادفع الآن لإعادة الاتصال والاستمتاع بخدمات اتصالات: etisalat.ae/quickpay
```

<a id="b2c-ex-sms-r006"></a>

#### B2C-EX-SMS-R006

Source: BANK / SMS_Final / row 6. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear $Name$, your account $Number$ has been cancelled upon your request. You will receive email shortly with full details.
```

**English after — source example**

```text
Hello $Name$. As requested, we've cancelled your account ($Number$). We'll send you a confirmation email soon. 
Don't forget – you still have XX unused Smiles points: <Link>
/
Remember, we're always here if you ever want to get back in touch.
```

**Arabic — source example**

```text
مرحباً $Name$، تم إلغاء الحساب ($Number$) حسب طلبك. ستتلقى رسالة بريد إلكتروني للتأكيد قريباً.
لا يزال لديك XX نقطة Smiles غير مستخدمة: <Link>

يسعدنا خدمتك مجدداً في أي وقت.
```

<a id="b2c-ex-sms-r007"></a>

#### B2C-EX-SMS-R007

Source: BANK / SMS_Final / row 7. Parent: B2C-SMS-001.

**English before — comparison only**

```text
The reported issue for the account <Acc> has been resolved. To view your fault resolution report, please visit <Link>
```

**English after — source example**

```text
Good news – we've fixed the issue on your account <Acc>. Read the full report here <Link>
```

**Arabic — source example**

```text
تم حل المشكلة في حسابك <Acc>. اعرف أكثر عبر التقرير الكامل هنا: <Link>
```

<a id="b2c-ex-sms-r008"></a>

#### B2C-EX-SMS-R008

Source: BANK / SMS_Final / row 8. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, your bill of AED $amount_due$ for account $account_number$ is due on $due_date$. Please pay now at www.etisalat.ae/quickpay
If you have already paid, please ignore this message. 
```

**English after — source example**

```text
Hello there, your bill of AED $amount_due$ for account $account_number$ is due on $due_date$. Pay now in a few taps through the etisalat UAE app, or at www.etisalat.ae/quickpay.

Already paid? Ignore this message.
```

**Arabic — source example**

```text
مرحباً، هناك فاتورة مستحقة السداد لحسابك بقيمة $amount_due$ درهم، وذلك بتاريخ $due_date$. يمكنك السداد الآن عبر تطبيق etisalat UAE أو عبر: www.etisalat.ae/quickpay
في حال تم السداد، يرجى تجاهل هذه الرسالة.
```

<a id="b2c-ex-sms-r009"></a>

#### B2C-EX-SMS-R009

Source: BANK / SMS_Final / row 9. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, your bill of AED $amount_due$ for account $account_number$ is due today. Please pay now at www.etisalat.ae/quickpay_x000B_If you have already paid, please ignore this message. 
```

**English after — source example**

```text
Hello there, your bill of AED $amount_due$ for account $account_number$ is due today. Please pay now in the etisalat UAE app.

Already paid? Ignore this message.
```

**Arabic — source example**

```text
مرحباً، فاتورة حسابك مستحقة اليوم بقيمة $amount_due$ درهم على الحساب $account_number$. سددها الآن عبر تطبيق etisalat UAE.
في حال تم السداد، يرجى تجاهل هذه الرسالة.
```

<a id="b2c-ex-sms-r010"></a>

#### B2C-EX-SMS-R010

Source: BANK / SMS_Final / row 10. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, your bill of AED $amount_due$ for account $account_number$ is overdue. To continue enjoying your services, please make a payment now at www.etisalat.ae/quickpay_x000B_If you have already paid, please ignore this message. 
```

**English after — source example**

```text
Important: your bill of AED $amount_due$ for account $account_number$ is overdue. Pay now in the etisalat UAE app to stay connected.

Already paid? Ignore this message.
```

**Arabic — source example**

```text
تنبيه هام: فاتورة حسابك $account_number$ متأخرة عن السداد بقيمة $amount_due$ درهم. سددها الآن عبر تطبيق etisalat UAE للاستمرار في استخدام الخدمة.
في حال تم السداد، يُرجى تجاهل هذه الرسالة.
```

<a id="b2c-ex-sms-r011"></a>

#### B2C-EX-SMS-R011

Source: BANK / SMS_Final / row 11. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Dear Customer, your bill of AED $amount_due$ for account $account_number$ is overdue. To avoid interruptions to your services and negative impact to your credit score with AECB, please make a payment now at www.etisalat.ae/quickpay._x000B_If you have already paid, please ignore this message. 
```

**English after — source example**

```text
Important: your bill of AED $amount_due$ for account $account_number$ is still outstanding. Not paying may affect your services, and even your credit score. Pay now in the etisalat UAE app.

Already paid? Ignore this message.
```

**Arabic — source example**

```text
تنبيه هام: لا تزال فاتورة حسابك بقيمة $amount_due$ درهم غير مسددة. قد يؤثر عدم السداد على خدماتك وتقييمك الائتماني. سدّدها الآن عبر تطبيق etisalat UAE.
في حال تم السداد، يُرجى تجاهل هذه الرسالة.
```

<a id="b2c-ex-sms-r012"></a>

#### B2C-EX-SMS-R012

Source: BANK / SMS_Final / row 12. Parent: B2C-SMS-001.

**English before — comparison only**

```text
Congratulations! You have subscribed to our Special Roaming Daily Data Offer successfully, you have been charged AED 17.50 (VAT not applicable) for one-time. Enjoy 500MB data for 24 hours starting from your first use with our preferred partners, check here for more details: www.etisalat.ae/preferredroamingpartners .To manage your add-ons, please visit www.etisalat.ae/manage
```

**English after — source example**

```text
You've subscribed to Special Roaming Daily Data Offer for AED 17.50 (excl. VAT)! Enjoy 500MB for 24 hours, which starts as soon as you use data abroad with one of our partners. 

Learn more at www.etisalat.ae/preferredroamingpartners. Or manage your add-ons in the etisalat UAE app. Thanks for choosing etisalat.
```

**Arabic — source example**

```text
تم الاشتراك في عرض البيانات اليومي للتجوال الخاص بقيمة 17.50 درهم (غير شامل ضريبة القيمة المضافة). استمتع بـ 500MB لمدة 24 ساعة، تبدأ المدة فور استخدام البيانات أثناء التجوال مع أحد شركائنا.
اعرف أكثر عبر: www.etisalat.ae/preferredroamingpartners أو يمكنك إدارة الإضافات عبر تطبيق etisalat UAE. شكراً لاختيارك اتصالات.
```

### BANK — Most Sent SMS_Final

Channel dependency: B2C-SMS-003. Populated examples: 21.

| Example ID | Source row | English-after preview |
| --- | --- | --- |
| [B2C-EX-SMS-MOST-R002](#b2c-ex-sms-most-r002) | 2 | Sorry, your balance is too low to subscribe to $ADDON_NAME$ (AED XX/mo). Please recharge and try again: $LINK$ |
| [B2C-EX-SMS-MOST-R003](#b2c-ex-sms-most-r003) | 3 | Your Daily 1GB Local Data Pack is active! Price: AED 5 (inc. VAT). It's valid for 1 day, in the UAE only. Unus… |
| [B2C-EX-SMS-MOST-R004](#b2c-ex-sms-most-r004) | 4 | You’ve reached the maximum subscription limit for $Plan_Name$. Manage your plans, packs, and add-ons in the et… |
| [B2C-EX-SMS-MOST-R005](#b2c-ex-sms-most-r005) | 5 | Thanks for using etisalat eRecharge. You’ve topped up $TOPUP_AMOUNT$ from $SPURCE_MERCHANT_ID$ on $TIMESTAMP_O… |
| [B2C-EX-SMS-MOST-R006](#b2c-ex-sms-most-r006) | 6 | Your $ACCOUNT_TYPE$ account ($ACCOUNT_NUMBER$) isn't active. Please activate your line in the etisalat UAE app… |
| [B2C-EX-SMS-MOST-R007](#b2c-ex-sms-most-r007) | 7 | We’re sorry, but your account isn't eligible for $Plan_Name$. Discover plans for you: $LINK$ |
| [B2C-EX-SMS-MOST-R008](#b2c-ex-sms-most-r008) | 8 | You can’t add $ADDON_NAME$ right now because your $PACKAGE$ isn’t compatible. Manage your packages in the etis… |
| [B2C-EX-SMS-MOST-R009](#b2c-ex-sms-most-r009) | 9 | $ADDON_NAME$ isn’t available on your current plan. Subscribe to a new plan and try again in the etisalat UAE a… |
| [B2C-EX-SMS-MOST-R010](#b2c-ex-sms-most-r010) | 10 | You've reached the maximum subscription limit for $Plan_Name$. Discover more plans, packs, and add-ons in the… |
| [B2C-EX-SMS-MOST-R011](#b2c-ex-sms-most-r011) | 11 | Your balance is low. Recharge via the etisalat UAE app and earn rewards every time. Need a credit transfer fro… |
| [B2C-EX-SMS-MOST-R012](#b2c-ex-sms-most-r012) | 12 | Hello $FIRST_NAME$, thanks for your payment – we've now processed it. Here are the details: Account number: $A… |
| [B2C-EX-SMS-MOST-R013](#b2c-ex-sms-most-r013) | 13 | Hello there, your bill for AED $amount_due$ is due soon (Account: $AccountNumberWithSuffix$). Pay in a few cli… |
| [B2C-EX-SMS-MOST-R014](#b2c-ex-sms-most-r014) | 14 | Sorry, $FIRST_NAME$, we can’t add $MOBILE_NO$ to your Smiles UAE membership $CARD_NO$. Learn more at https://s… |
| [B2C-EX-SMS-MOST-R015](#b2c-ex-sms-most-r015) | 15 | Congratulations $FIRST_NAME$! You’ve earned $pts$ Smiles Points from $partner_name$ for $activity_description$… |
| [B2C-EX-SMS-MOST-R016](#b2c-ex-sms-most-r016) | 16 | Great news, $FIRST_NAME$! You've just earned $TOTAL_POINTS$ Smiles Points and a $TIER_BONUS$ tier bonus for yo… |
| [B2C-EX-SMS-MOST-R017](#b2c-ex-sms-most-r017) | 17 | Hello there, you haven't used your prepaid line since $DATE$. Start today to keep enjoying your service and be… |
| [B2C-EX-SMS-MOST-R018](#b2c-ex-sms-most-r018) | 18 | $CUSTOMER_FIRSTNAME$, you just paid $CURRENCY$ $AMOUNT$ to $MERCHANT_NAME$ with your etisalat money card endin… |
| [B2C-EX-SMS-MOST-R019](#b2c-ex-sms-most-r019) | 19 | $SENDER_NAME$, you’ve sent AED $AMOUNT$ ($FX_CURRENCY$ $RECEIVE_AMOUNT$) to $RECEIVER_NAME$. We'll let you kno… |
| [B2C-EX-SMS-MOST-R020](#b2c-ex-sms-most-r020) | 20 | Transfer successful! $RECEIVER_NAME$ just got $FX_CURRENCY$ $RECEIVE_AMOUNT$. $PARTNER_NAME$ reference: $MG_RE… |
| [B2C-EX-SMS-MOST-R021](#b2c-ex-sms-most-r021) | 21 | Here's your one-time password for the etisalat UAE app: $CODE$. Never share this code. Didn't request a code?… |
| [B2C-EX-SMS-MOST-R022](#b2c-ex-sms-most-r022) | 22 | Welcome to Oman. Dial *177# for 500MB (AED 35/day) to get you started. Then go to "add-ons" in the etisalat UA… |

<a id="b2c-ex-sms-most-r002"></a>

#### B2C-EX-SMS-MOST-R002

Source: BANK / Most Sent SMS_Final / row 2. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Your subscription request cannot be completed due to low balance in your account. Kindly recharge and try again.
```

**English after — source example**

```text
Sorry, your balance is too low to subscribe to $ADDON_NAME$ (AED XX/mo). Please recharge and try again: $LINK$
```

**Arabic — source example**

```text
عذراً، رصيدك الحالي غير كافي للاشتراك في $ADDON_NAME$ ($XX درهماً شهرياً). يرجى إعادة تعبئة الرصيد ثم المحاولة مرة أخرى: $LINK$
```

<a id="b2c-ex-sms-most-r003"></a>

#### B2C-EX-SMS-MOST-R003

Source: BANK / Most Sent SMS_Final / row 3. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear customer, your request to subscribe to Daily 1GB local data pack has been completed successfully, and AED 5 (Including 5% VAT) has been debited from your account balance.
Pack is onetime valid for 1 day and data can be used within UAE only. Any unused data post expiry will be fortified. To check your remaining data allowance send DATA to 1010. To manage your subscription visit etisalat UAE app.
```

**English after — source example**

```text
Your Daily 1GB Local Data Pack is active! Price: AED 5 (inc. VAT). It's valid for 1 day, in the UAE only. Unused data will expire. Check your remaining data and manage everything in the etisalat UAE app.
```

**Arabic — source example**

```text
تم تفعيل باقة البيانات المحلية اليومية (1GB). الرسوم: 5 دراهم (شامل ضريبة القيمة المضافة). سيتم مصادرة البيانات غير المستخدمة بعد انتهاء صلاحيتها خلال يوم واحد داخل دولة الإمارات فقط. قم بالتحقّق من الرصيد المتبقي وإدارة الباقة عبر تطبيق etisalat UAE.
```

<a id="b2c-ex-sms-most-r004"></a>

#### B2C-EX-SMS-MOST-R004

Source: BANK / Most Sent SMS_Final / row 4. Parent: B2C-SMS-003.

**English before — comparison only**

```text
 You have reached maximum subsription limit for the   $Plan_Name$  .
```

**English after — source example**

```text
You’ve reached the maximum subscription limit for $Plan_Name$. Manage your plans, packs, and add-ons in the etisalat UAE app: $LINK$
```

**Arabic — source example**

```text
تم الوصول إلى الحد الأقصى للاشتراك في $Plan_Name$. يمكنك إدارة باقاتك والإضافات عبر تطبيق etisalat UAE: $LINK$
```

<a id="b2c-ex-sms-most-r005"></a>

#### B2C-EX-SMS-MOST-R005

Source: BANK / Most Sent SMS_Final / row 5. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Thank you for using etisalat eRecharge Service. Your mobile account has been top up for $TOPUP_AMOUNT$ from $SPURCE_MERCHANT_ID$ on $TIMESTAMP_OF_TOPUP$ . TxnId: $TRANSACTION_ID$
```

**English after — source example**

```text
Thanks for using etisalat eRecharge. You’ve topped up $TOPUP_AMOUNT$ from $SPURCE_MERCHANT_ID$ on $TIMESTAMP_OF_TOPUP$. TxnId: $TRANSACTION_ID$. New balance: $NEW_BALANCE$
```

**Arabic — source example**

```text
شكراً لاستخدامك اتصالات eRecharge. تمت إعادة تعبئة الرصيد $TOPUP_AMOUNT$ من $SPURCE_MERCHANT_ID$ بتاريخ $TIMESTAMP_OF_TOPUP$. رقم العملية: $TRANSACTION_ID$ رصيدك الحالي: $NEW_BALANCE$
```

<a id="b2c-ex-sms-most-r006"></a>

#### B2C-EX-SMS-MOST-R006

Source: BANK / Most Sent SMS_Final / row 6. Parent: B2C-SMS-003.

**English before — comparison only**

```text
 Your account is not active. Kindly activate your line and try again.
```

**English after — source example**

```text
Your $ACCOUNT_TYPE$ account ($ACCOUNT_NUMBER$) isn't active. Please activate your line in the etisalat UAE app within $TIMEFRAME$ and try again: $LINK$
```

**Arabic — source example**

```text
حساب $ACCOUNT_TYPE$ ($ACCOUNT_NUMBER$) غير نشط حالياً. يرجى تفعيل الخط عبر تطبيق etisalat UAE خلال $TIMEFRAME$ ثم المحاولة مرة أخرى: $LINK$
```

<a id="b2c-ex-sms-most-r007"></a>

#### B2C-EX-SMS-MOST-R007

Source: BANK / Most Sent SMS_Final / row 7. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Sorry, you are not eligible for  $Plan_Name$ .
```

**English after — source example**

```text
We’re sorry, but your account isn't eligible for $Plan_Name$. Discover plans for you: $LINK$
```

**Arabic — source example**

```text
حسابك غير مؤهل للاشتراك في $Plan_Name$. قم بالاطلاع على الباقات المتاحة لك هنا: $LINK$
```

<a id="b2c-ex-sms-most-r008"></a>

#### B2C-EX-SMS-MOST-R008

Source: BANK / Most Sent SMS_Final / row 8. Parent: B2C-SMS-003.

**English before — comparison only**

```text
You cannot subscribe to  $ADDON_NAME$ . as you have an active package that does not coexist with the requested offer.
```

**English after — source example**

```text
You can’t add $ADDON_NAME$ right now because your $PACKAGE$ isn’t compatible. Manage your packages in the etisalat UAE app.
```

**Arabic — source example**

```text
لا يمكن إضافة $ADDON_NAME$ حالياً لعدم توافقها مع باقتك. قم بإدارة باقاتك عبر تطبيق etisalat UAE.
```

<a id="b2c-ex-sms-most-r009"></a>

#### B2C-EX-SMS-MOST-R009

Source: BANK / Most Sent SMS_Final / row 9. Parent: B2C-SMS-003.

**English before — comparison only**

```text
The requested addon  $ADDON_NAME$  is not available for subscription on your number, please subscribe to the parent plan, then try again. To buy another addon, dial *101# or visit www.etisalat.ae/addon
```

**English after — source example**

```text
 $ADDON_NAME$ isn’t available on your current plan. Subscribe to a new plan and try again in the etisalat UAE app.
```

**Arabic — source example**

```text
$ADDON_NAME$ غير متاحة لباقتك الحالية. اشترك في باقة أخرى ثم أعد المحاولة عبر تطبيق etisalat UAE.
```

<a id="b2c-ex-sms-most-r010"></a>

#### B2C-EX-SMS-MOST-R010

Source: BANK / Most Sent SMS_Final / row 10. Parent: B2C-SMS-003.

**English before — comparison only**

```text
You have exceeded the maximum number of times you can subscribe to $Plan_Name$ .
```

**English after — source example**

```text
You've reached the maximum subscription limit for $Plan_Name$. Discover more plans, packs, and add-ons in the etisalat UAE app.
```

**Arabic — source example**

```text
لقد تم الوصول إلى الحد الأقصى للاشتراك في $Plan_Name$. اطّلع على المزيد من الباقات والإضافات عبر تطبيق etisalat UAE.
```

<a id="b2c-ex-sms-most-r011"></a>

#### B2C-EX-SMS-MOST-R011

Source: BANK / Most Sent SMS_Final / row 11. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Your balance is getting low. Recharge your account online and get special offers on every recharge at etisalat.ae/recharge . You can also request credit transfer from your friends and family by dialing *107*05XXXXXX*Amount#
```

**English after — source example**

```text
Your balance is low. Recharge via the etisalat UAE app and earn rewards every time. Need a credit transfer from friends or family? You can do that in the app too.
```

**Arabic — source example**

```text
رصيدك غير كافِ. أعد تعبئة الرصيد عبر تطبيق etisalat UAE واستفد من المكافآت في كل مرة. هل تحتاج إلى تحويل رصيد من الأهل أو الأصدقاء؟ يمكنك إتمام ذلك عبر التطبيق أيضاً.
```

<a id="b2c-ex-sms-most-r012"></a>

#### B2C-EX-SMS-MOST-R012

Source: BANK / Most Sent SMS_Final / row 12. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear Customer, Your payment to the account number $ACCOUNT_NUMBER$  has been processed.
Amount Due: AED $DUE_AMOUNT$ 
Amount Paid: AED $PAID_AMOUNT$ 
Remaining Balance: AED $BALANCE_AMOUNT$ 
Transaction Date: $TXN_DATE$ 
Transaction Time: $TXN_TIME$ 
Payment Channel: $PAYMENT_CHANNEL$ 
Card Number: $CARD_NUMBER$ 
Mode of Payment : $MODE_OF_PAYMENT$ 
Transaction #: $TXN_NUMBER$ 
Reference #: $EPG_REFRENCE_NUMBER$ 

To Know your Payment Status through WhatsApp Click on  $WhatsAppURL$ 
```

**English after — source example**

```text
Hello $FIRST_NAME$, thanks for your payment – we've now processed it. Here are the details:

Account number: $ACCOUNT_NUMBER$ 
Amount Due: AED $DUE_AMOUNT$ 
Amount Paid: AED $PAID_AMOUNT$ 
Remaining Balance: AED $BALANCE_AMOUNT$ 
Transaction Date: $TXN_DATE$ 
Transaction Time: $TXN_TIME$ 
Payment Channel: $PAYMENT_CHANNEL$ 
Card Number: $CARD_NUMBER$ 
Mode of Payment: $MODE_OF_PAYMENT$ 
Transaction #: $TXN_NUMBER$ 
Reference #: $EPG_REFERENCE_NUMBER$ 

View your payment status via WhatsApp [$WhatsAppURL$]
```

**Arabic — source example**

```text
مرحباً $FIRST_NAME$، شكراً لإتمام عملية الدفع، تمّ تنفيذها بنجاح. إليك التفاصيل كما يلي:

رقم الحساب: $ACCOUNT_NUMBER$
المبلغ المستحق: $DUE_AMOUNT$
المبلغ المدفوع: $PAID_AMOUNT$ درهم
الرصيد المتبقي: $BALANCE_AMOUNT$ درهم
تاريخ العملية: $TXN_DATE$ درهم
وقت العملية: $TXN_TIME$
قناة الدفع: $PAYMENT_CHANNEL$
رقم البطاقة: $CARD_NUMBER$
طريقة الدفع: $MODE_OF_PAYMENT$
رقم العملية: $TXN_NUMBER$
الرقم المرجعي: $EPG_REFERENCE_NUMBER$

اطّلع على حالة الدفع من خلال WhatsApp: [$WhatsAppURL$]
```

<a id="b2c-ex-sms-most-r013"></a>

#### B2C-EX-SMS-MOST-R013

Source: BANK / Most Sent SMS_Final / row 13. Parent: B2C-SMS-003.

**English before — comparison only**

```text
AED $amount_due$ due on account no. $AccountNumberWithSuffix$ . To avoid further reminders, pay it online here www.etisalat.ae/quickpay. You can also use our payment machine or call 125 with your account ID $account_id$ . For more assistance, call $DCA_Inbound_Number$ . Please ignore this message if you’ve already paid.
```

**English after — source example**

```text
Hello there, your bill for AED $amount_due$ is due soon (Account: $AccountNumberWithSuffix$). Pay in a few clicks in the etisalat UAE app.

Already paid? Ignore this message.
```

**Arabic — source example**

```text
مرحباً، لديك مبلغ مستحق بقيمة $amount_due$ درهم على الحساب ($AccountNumberWithSuffix$)، وسيحين موعد السداد قريباً. سدد فاتورتك بسهولة عبر تطبيق etisalat UAE.
في حال تم السداد، يُرجى تجاهل هذه الرسالة.
```

<a id="b2c-ex-sms-most-r014"></a>

#### B2C-EX-SMS-MOST-R014

Source: BANK / Most Sent SMS_Final / row 14. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear  $FIRST_NAME$   , we are unable to process your request to add account no $MOBILE_NO$ under your Smiles UAE membership number $CARD_NO$  .  Know more about Smiles at https://smilesuae.ae/appdownload 
```

**English after — source example**

```text
Sorry, $FIRST_NAME$, we can’t add $MOBILE_NO$ to your Smiles UAE membership $CARD_NO$. Learn more at https://smilesuae.ae/appdownload
```

**Arabic — source example**

```text
عذراً $FIRST_NAME$، لا يمكن إضافة $MOBILE_NO$ إلى عضوية Smiles UAE $CARD_NO$ حالياً. اعرف أكثر عبر: https://smilesuae.ae/appdownload
```

<a id="b2c-ex-sms-most-r015"></a>

#### B2C-EX-SMS-MOST-R015

Source: BANK / Most Sent SMS_Final / row 15. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear $FIRST_NAME$ , Congratulations! You have earned $pts$ points from $partner_name$ for $activity_description$ . Your current points balance is $xxx$ . FREE Delivery on every grocery order from Smiles Market. Order now https://smilesuae.go.link/fNfsU
```

**English after — source example**

```text
Congratulations $FIRST_NAME$! You’ve earned $pts$ Smiles Points from $partner_name$ for $activity_description$. Your new balance is $xxx$. You also get free delivery on every grocery order from Smiles Market. Order now: https://smilesuae.go.link/fNfsU
```

**Arabic — source example**

```text
تهانينا $FIRST_NAME$! لقد حصلت على $pts$ نقطة Smiles من $partner_name$ مقابل $activity_description$. رصيدك الحالي: $xxx$. كما ستحصل أيضاً على توصيل مجاني على جميع طلبات البقالة من Smiles Market. اطلب الآن: https://smilesuae.go.link/fNfsU
```

<a id="b2c-ex-sms-most-r016"></a>

#### B2C-EX-SMS-MOST-R016

Source: BANK / Most Sent SMS_Final / row 16. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear $FIRST_NAME$, Great news! You've just earned $TOTAL_POINTS$ usage points and an additional $TIER_BONUS$ tier bonus for your $ACCRUAL_DESCRIPTION$ on account number $MSISDN$. To discover more benefits and rewards, visit the Smiles app today!
```

**English after — source example**

```text
Great news, $FIRST_NAME$! You've just earned $TOTAL_POINTS$ Smiles Points and a $TIER_BONUS$ tier bonus for your $ACCRUAL_DESCRIPTION$. Discover more rewards on the Smiles app: https://smilesuae.go.link/fNfsU 
```

**Arabic — source example**

```text
خبر سار يا $FIRST_NAME$! لقد حصلت على $TOTAL_POINTS$ نقطة Smiles، بالإضافة إلى مكافأة فئة بقيمة $TIER_BONUS$ مقابل $ACCRUAL_DESCRIPTION$. اكتشف المزيد من المكافآت عبر تطبيق Smiles: https://smilesuae.go.link/fNfsU
```

<a id="b2c-ex-sms-most-r017"></a>

#### B2C-EX-SMS-MOST-R017

Source: BANK / Most Sent SMS_Final / row 17. Parent: B2C-SMS-003.

**English before — comparison only**

```text
You have not used your prepaid line since $DATE$ . Please start using it today to keep enjoying your validity benefits.

For more details, visit www.etisalat.ae/waselvalidityrulesen.
```

**English after — source example**

```text
Hello there, you haven't used your prepaid line since $DATE$. Start today to keep enjoying your service and benefits. Learn more at www.etisalat.ae/waselvalidityrulesen
```

**Arabic — source example**

```text
مرحباً، لم يتم استخدام خطك المدفوع مقدماً منذ $DATE$. استخدم خطك اليوم للحفاظ على الخدمة والاستفادة من المزايا. اعرف أكثر: www.etisalat.ae/waselvalidityrulesen
```

<a id="b2c-ex-sms-most-r018"></a>

#### B2C-EX-SMS-MOST-R018

Source: BANK / Most Sent SMS_Final / row 18. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Dear $CUSTOMER_FIRSTNAME$, a purchase of $CURRENCY$ $AMOUNT$ was successfully completed at $MERCHANT_NAME$ using your etisalat money card ending with $LAST_DIGITS_CARD$. 
Date: $DATE_TIME$
You earned AED $REWARD_AMOUNT$ cash rewards with this transaction.
Available balance: AED $AVAILABLE_BALANCE$
Transaction ID: $TRANSACTION_ID$
```

**English after — source example**

```text
$CUSTOMER_FIRSTNAME$, you just paid $CURRENCY$ $AMOUNT$ to $MERCHANT_NAME$ with your etisalat money card ending in $LAST_DIGITS_CARD$. 

You've earned AED $REWARD_AMOUNT$ and your balance is now AED $AVAILABLE_BALANCE$.

Date: $DATE_TIME$
Transaction ID: $TRANSACTION_ID$
```

**Arabic — source example**

```text
$CUSTOMER_FIRSTNAME$، تم تنفيذ عملية دفع $AMOUNT$ $CURRENCY$ لدى $MERCHANT_NAME$ باستخدام بطاقة etisalat money المنتهية بـ$LAST_DIGITS_CARD$.
لقد حصلت على $REWARD_AMOUNT$ درهم، وأصبح رصيدك الآن $AVAILABLE_BALANCE$ درهم.
التاريخ: $DATE_TIME$
رقم العملية: $TRANSACTION_ID$
```

<a id="b2c-ex-sms-most-r019"></a>

#### B2C-EX-SMS-MOST-R019

Source: BANK / Most Sent SMS_Final / row 19. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Hey $SENDER_NAME$! 
Your transfer of AED $AMOUNT$ is initiated. 
You'll get an alert when $RECEIVER_NAME$ receives the amount of $FX_CURRENCY$ $RECEIVE_AMOUNT$ in their $BANK_NAME$ account. 
Your $PARTNER_NAME$ reference number: $MG_REFERENCE_NUMBER$
```

**English after — source example**

```text
$SENDER_NAME$, you’ve sent AED $AMOUNT$ ($FX_CURRENCY$ $RECEIVE_AMOUNT$) to $RECEIVER_NAME$. We'll let you know when it arrives. 
$PARTNER_NAME$ reference: $MG_REFERENCE_NUMBER$
```

**Arabic — source example**

```text
$SENDER_NAME$، تم إرسال $AMOUNT$ درهم ($FX_CURRENCY$ $RECEIVE_AMOUNT$) إلى $RECEIVER_NAME$. سنقوم بإبلاغك عند وصول المبلغ. الرقم المرجعي $PARTNER_NAME$: $MG_REFERENCE_NUMBER$
```

<a id="b2c-ex-sms-most-r020"></a>

#### B2C-EX-SMS-MOST-R020

Source: BANK / Most Sent SMS_Final / row 20. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Woohoo, $SENDER_NAME$ 
Your transfer is done! 
$RECEIVER_NAME$ received $FX_CURRENCY$ $RECEIVE_AMOUNT$ successfully! 
Seamless and successful – just how we like it! 
Your $PARTNER_NAME$ reference number: $MG_REFERENCE_NUMBER$
```

**English after — source example**

```text
Transfer successful! $RECEIVER_NAME$ just got $FX_CURRENCY$ $RECEIVE_AMOUNT$. 

$PARTNER_NAME$ reference: $MG_REFERENCE_NUMBER$

Thanks for using etisalat Money.
```

**Arabic — source example**

```text
تمت عملية التحويل بنجاح! استلم $RECEIVER_NAME$ مبلغ $FX_CURRENCY$ $RECEIVE_AMOUNT$.
الرقم المرجعي $PARTNER_NAME$: $MG_REFERENCE_NUMBER$
شكراً لاستخدامك etisalat money.
```

<a id="b2c-ex-sms-most-r021"></a>

#### B2C-EX-SMS-MOST-R021

Source: BANK / Most Sent SMS_Final / row 21. Parent: B2C-SMS-003.

**English before — comparison only**

```text
<#> $CODE$  is the security code. This is a One-Time Password (OTP) from the etisalat UAE Portal/Mobile App that will grant you access to manage or allow the purchase of service on your account/s. Do not disclose this to anyone as your account can be compromised. If you’ve not requested this, please contact us on 101.0rkaqIiy6Fg
```

**English after — source example**

```text
Here's your one-time password for the etisalat UAE app: $CODE$. Never share this code. Didn't request a code? Call us now on 101.
```

**Arabic — source example**

```text
إليك رمز التحقق لتطبيق etisalat UAE: $CODE$ لا تشارك هذا الرمز مع أي شخص. إذا لم تطلب هذا الرمز، اتصل بنا فوراً على 101.
```

<a id="b2c-ex-sms-most-r022"></a>

#### B2C-EX-SMS-MOST-R022

Source: BANK / Most Sent SMS_Final / row 22. Parent: B2C-SMS-003.

**English before — comparison only**

```text
Welcome to Oman. Stay connected with your loved ones with ease. Dial *177# to get a 500MB mobile internet data roaming pack for just AED 35 per day. To view other roaming packages with voice options as well, and to check standard roaming rates and more information, dial *177# or order through etisalat UAE app (Consumer) or etisalat UAE Business app (Business). We wish you a great stay
```

**English after — source example**

```text
Welcome to Oman. Dial *177# for 500MB (AED 35/day) to get you started. Then go to "add-ons" in the etisalat UAE app to discover our Roam Like Home packs, rates, and more. If you have a business account, you can manage roaming in the etisalat Business app. 

Enjoy Oman with etisalat.
```

**Arabic — source example**

```text
مرحباً بك في عُمان.
اطلب *177# للحصول على 500MB مقابل 35 درهماً يومياً.
لاكتشاف باقات تجوّل كأنك في دارك والأسعار وأكثر، افتح صفحة الإضافات في تطبيق etisalat UAE. وإذا كان لديك حساب أعمال، يمكنك إدارة التجوال عبر تطبيق etisalat Business.
استمتع بإقامتك في عُمان مع اتصالات.
```

### BANK — Email_Final

Channel dependency: B2C-EMAIL-001. Populated examples: 9.

| Example ID | Source row | English-after preview |
| --- | --- | --- |
| [B2C-EX-EMAIL-R002](#b2c-ex-email-r002) | 2 | Subject: Don't forget – your offer expires soon Account number: (Acc. Number: DD, MM, YYYY) Header: A world of… |
| [B2C-EX-EMAIL-R003](#b2c-ex-email-r003) | 3 | [FIRST EMAIL] Subject: Your first bill is on its way – here's what you need to know Header: What to expect fro… |
| [B2C-EX-EMAIL-R004](#b2c-ex-email-r004) | 4 | Subject: Important: Your outgoing calls and data have been suspended Header: Pay now to reconnect Body: Hello… |
| [B2C-EX-EMAIL-R005](#b2c-ex-email-r005) | 5 | Subject: Important: Your etisalat services have been suspended Header: Pay now Body: You have missed your "Pro… |
| [B2C-EX-EMAIL-R006](#b2c-ex-email-r006) | 6 | Subject: Make home smarter and safer with the $New Neo Smart Home Plan$ Header: 5 upgrades. AED 100/month. Tha… |
| [B2C-EX-EMAIL-R007](#b2c-ex-email-r007) | 7 | Subject: Your etisalat device is now protected – enjoy peace of mind Body: Hello there, Great news – your $Dev… |
| [B2C-EX-EMAIL-R008](#b2c-ex-email-r008) | 8 | Subject: Important: Your bill is due today Header: Make a payment today Body: Hello there, Your bill for $amou… |
| [B2C-EX-EMAIL-R009](#b2c-ex-email-r009) | 9 | Subject: Welcome to $Parental Control$ Header: Keeping your family safe Body: Hello there, Thanks for subscrib… |
| [B2C-EX-EMAIL-R010](#b2c-ex-email-r010) | 10 | Subject: Urgent: data and SMS roaming restrictions in Russia Header: What you need to know Body: Dear Customer… |

<a id="b2c-ex-email-r002"></a>

#### B2C-EX-EMAIL-R002

Source: BANK / Email_Final / row 2. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject:        Your Account`s Offer is Nearing to Expire
Account Number: DD, MM, YYY
Header:         Your Offer will Expire Soon
Para 1:        Dear Customer,        We want to inform you that your current $Offer Name$ benefits package for your $Service Name$ will expire on $Date$.
Para 2:        Post-Expiration Details:
         Benefits: $List of benefits$
         Monthly Fee: AED $Monthly Price$
Para 3:        To ensure uninterrupted service and continue enjoying your benefits, please take action before the expiration date. 
You can easily manage your account through $etisalat UAE app$
Para 4:        View & pay your bill easily on the etisalat UAE app DOWNLOAD NOW
Footer: Copyright 2024 @ etisalat. All Rights Reserved. This is an auto generated email sent by our system. Please do not reply to this email.
```

**English after — source example**

```text
Subject:        
Don't forget – your offer expires soon

Account number: 
(Acc. Number: DD, MM, YYYY)

Header:         
A world of more is waiting

Body:      
Hello there,      

Just so you know, your $Offer Name$ benefits package for your $Service Name$ will expire on $Date$.

Once it's expired, your plan will cost AED $Monthly Price$/month, and have these benefits:

$List of benefits$

You can manage your plan, benefits, and more in the etisalat UAE app.
 
App line:        
Don’t have the etisalat UAE app? Download now.

Footer: Copyright 2024 @ etisalat. All Rights Reserved. This is an auto generated email sent by our system. Please do not reply to this email.
```

**Arabic — source example**

```text
لا تفوّت الفرصة، سينتهي العرض قريباً

رقم الحساب:
(Acc. Number: DD, MM, YYYY)

دايماً في أكثر مما تتوقع

 مرحباً،

نودّ تذكيرك بانتهاء صلاحية مزايا باقة $Offer Name$ الخاصة بخدمة $Service Name$ بتاريخ $Date$.

بعد انتهاء العرض، سيتم احتساب الاشتراك بقيمة $Monthly Price$ درهماً شهرياً، مع المزايا التالية:

 $List of benefits$ 

يمكنك إدارة باقتك، المزايا وأكثر بسهولة عبر تطبيق etisalat UAE.

نزّل تطبيق etisalat UAE الآن

© 2024 اتصالات. جميع الحقوق محفوظة. تم إرسال هذا البريد الإلكتروني تلقائياً. يرجى عدم الرد عليه.
```

<a id="b2c-ex-email-r003"></a>

#### B2C-EX-EMAIL-R003

Source: BANK / Email_Final / row 3. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Header: What to expect from your first bill
Account Number: < Acc>
DD, MM, YYYY
Your first bill is almost here!
Dear Customer,
Your first etisalat bill for account number <Number> will be issued on the 1st of every month. 
To help you understand your first bill, we have created a short video showing how you to read your bill, first month charges explained, applicable promotions, and bill payment guidance.
Add Video
{H1} Important Notes About Your First Bill
{H2} Pro-Rata Charges
Your first bill will be pro-rated to reflect the actual days of service used during the month. This means you will only be charged for the days from when your service was first activated.
How Does Pro-Rating Work?
If you subscribed to a plan costing AED 150 per month on November 16th. Your pro-rata charges for the month of November will be calculated as follows:
Please note that pro-rated fees are calculated assuming a 30-day month. Actual charges will vary based on the specific number of days in the billing months and your service activation date.
{H2} Rental Discounts 
If you subscribed using any promotional offers or discounts, then the Rental discounts will be applied from your 2nd month to maximize your promotion benefits.
Understand your etisalat bill with the Bill Explainer tool. Visit Bill Explainer
To know more about the other payment channels, please visit this link 
To manage your account, bill payments, account recharge, data sharing, and more ...
Download etisalat UAE app
IOS           Android
Thank you for choosing etisalat. Hope to see you again.
etisalat UAE app links
Have a good day
Copyright 2024 @ etisalat. All Rights Reserved. This is an auto generated email sent by our system. Please do not reply to this email
```

**English after — source example**

```text
[FIRST EMAIL]

Subject:
Your first bill is on its way – here's what you need to know

Header:
What to expect from your first bill

Account Number:
(Acc. Number: DD, MM, YYYY)

Hello there, 

Your first bill is on its way. We'll issue it at the start of every month, and it will reflect your previous month's charges.

To help you understand your first bill, watch the short video below. It explains first month charges, how to read your bill, how you can apply promotions, and the easiest ways to pay. 

[VIDEO]

[SECOND EMAIL]

Subject:
Your guide to pro-rata charges

Header:
What you need to know

Account Number:
(Acc. Number: DD, MM, YYYY)

Hello there,

Your first bill will only reflect the days you use your plan. You won't be charged for any days before your plan is activated. Here's an example:

[EXAMPLE]

We also calculate daily rates using a typical 30-day month. But because actual months can be longer or shorter, and depending on when you activate your plan, your daily charges may vary slightly. Don't worry – your monthly cost hasn't changed.

[THIRD EMAIL]

Subject:
Your guide to subscription discounts

Header:
What you need to know

Account Number:
(Acc. Number: DD, MM, YYYY)

Hello there,

If you subscribed to etisalat using a promotional offer or discount, we'll apply this from your first full month. That way you get the most from the offer.

And remember, you can manage your account, plan, benefits, and more in the etisalat UAE app. You can also automate your payments with Autopay. Don’t have the etisalat UAE app? Download now. [$Link$]

Learn more about your etisalat bill with our Bill Explainer tool [$Link$]

Footer of all emails:
Thank you for choosing etisalat. Welcome to a world of more.
Copyright 2025 @ etisalat. All Rights Reserved. This is an auto generated email sent by our system. Please do not reply to this email
```

**Arabic — source example**

```text
[FIRST EMAIL]
Subject:
فاتورتك الأولى قيد الإصدار 
رقم الحساب:
(Acc. Number: DD, MM, YYYY)
إليك كل ما تحتاج معرفته عن فاتورتك الأولى
مرحباً،
فاتورتك الأولى قيد الإصدار، وسيتم إصدارها في بداية كل شهر، لتعكس الرسوم المستحقة عن الشهر السابق.
ولمساعدتك في الاطلاع على تفاصيل فاتورتك الأولى وفهمها بشكل أوضح، يمكنك مشاهدة الفيديو القصير أدناه، حيث يشرح:
رسوم الشهر الأول
طريقة الاطلاع على الفاتورة
كيفية الاستفادة من العروض الترويجية
أسهل طرق السداد
[VIDEO]
شكراً لاختيارك اتصالات.
© 2025 اتصالات. جميع الحقوق محفوظة.
تم إرسال هذا البريد الإلكتروني تلقائياً، يرجى عدم الرد عليه.
[SECOND EMAIL]
Subject:
آلية احتساب الرسوم حسب مدة الاستخدام
رقم الحساب:
(Acc. Number: DD, MM, YYYY)
إليك كيفية احتساب الرسوم في فاتورتك الأولى
مرحباً،
ستتضمن فاتورتك الأولى الرسوم الخاصة بالأيام التي استخدمت فيها باقتك فقط، ولن يتم احتساب أي رسوم عن الفترة التي سبقت تفعيل الاشتراك.
فيما يلي مثال توضيحي:
[EXAMPLE]
يتم احتساب المعدل اليومي للرسوم على أساس  30 يوماً في الشهر، ونظراً لاختلاف عدد أيام الأشهر ، أو بحسب تاريخ تفعيل باقتك، قد يظهر فرق بسيط في قيمة الرسوم اليومية.
لكن لا داعي للقلق، فقيمة اشتراكك الشهرية ثابتة ولم تتغير.
شكرًا لاختيارك اتصالات.
© 2025 اتصالات. جميع الحقوق محفوظة.
تم إرسال هذا البريد الإلكتروني تلقائياً، يرجى عدم الرد عليه.
[THIRD EMAIL]
Subject:
كيفية تطبيق الخصومات على اشتراكك
رقم الحساب:
(Acc. Number: DD, MM, YYYY)
إليك طريقة تطبيق الخصومات على اشتراكك
مرحباً،
في حال اشتراكك في اتصالات من خلال عرض ترويجي أو خصمٍ ما، سيتم تطبيق هذا العرض ابتداءً من أول شهر كامل من الاشتراك، وذلك لضمان استفادتك الكاملة من المزايا المتاحة.
ويمكنك في أي وقت إدارة حسابك وباقتك والمزايا المرتبطة بها عبر تطبيق etisalat UAE، كما يمكنك تفعيل الدفع التلقائي (Autopay) لتسهيل إدارة مدفوعاتك.

نزّل تطبيق etisalat UAE الآن: [$Link$]
لمزيد من المعلومات حول فاتورتك:
[$Link$]
شكرًا لاختيارك اتصالات.
© 2025 اتصالات. جميع الحقوق محفوظة.
تم إرسال هذا البريد الإلكتروني تلقائياً، يرجى عدم الرد عليه.

```

<a id="b2c-ex-email-r004"></a>

#### B2C-EX-EMAIL-R004

Source: BANK / Email_Final / row 4. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject:
Service Suspension Notice due to Non-Payment Bill

Header:
Service Suspension due to Outstanding Payment

Body:
Dear Customer, 
We are informing you that your account $account_number$ has exceeded the "Promise to Pay" commitment deadline without receiving the payment. Due to an outstanding balance of AED $amount_due$, we have temporarily suspended outgoing calls and data services on your account.

To restore your services without further delay, please make the payment of the outstanding balance by visiting etisalat.ae/quickpay. Once your payment is processed, all services will be automatically restored. Thank you for choosing etisalat.
```

**English after — source example**

```text
Subject:
Important: Your outgoing calls and data have been suspended

Header:
Pay now to reconnect

Body:
Hello there, 

You haven’t paid your bill for AED $amount_due$ on account $account_number$. This means you’ve now exceeded your "Promise to Pay" commitment, and your outgoing calls and data have been suspended. 

This may affect your ability to enjoy etisalat services in the future.

Pay now to reconnect with everything etisalat. 

CTA: Pay now

Thank you

The etisalat Team
```

**Arabic — source example**

```text
Subject:
تنبيه هام: تم إيقاف المكالمات الصادرة والبيانات مؤقتاً
Header:
ادفع الآن لاستعادة الخدمة
مرحباً،
لم يتم سداد مبلغ $amount_due$ درهم المستحق على الحساب $account_number$، ونتيجة لذلك تم تجاوز الموعد المتفق عليه للسداد، ما أدى إلى إيقاف المكالمات الصادرة وخدمة البيانات مؤقتاً.
قد يؤثر ذلك على استمرار استفادتك من خدمات اتصالات مستقبلاً.
يمكنك السداد الآن لإعادة تفعيل الخدمة والاستمتاع بخدمات اتصالات من جديد.
CTA:
ادفع الآن
شكراً لك،
فريق اتصالات
```

<a id="b2c-ex-email-r005"></a>

#### B2C-EX-EMAIL-R005

Source: BANK / Email_Final / row 5. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject:
Your etisalat Services Have Been Suspended

Header:
Imediate Action Needed

Body:
Dear Customer,
We are informing you that your account $account_number$ has exceeded the "Promise to Pay" commitment deadline without receiving the payment. Due to an outstanding balance of AED $amount_due$, we have temporarily suspended all services on your account.

To restore your services without further delay, please make the payment of the outstanding balance by visiting etisalat.ae/quickpay. Once your payment is processed, all services will be automatically restored. Thank you for choosing etisalat.
```

**English after — source example**

```text
Subject:
Important: Your etisalat services have been suspended

Header:
Pay now

Body:
You have missed your "Promise to Pay" deadline for AED $amount_due$ on account $account_number$. All of your services are now suspended.

This may impact your credit score, and affect your ability to use etisalat in the future.

Pay now to reconnect. 

CTA: Pay now

Thank you

The etisalat Team

```

**Arabic — source example**

```text
Subject:
تنبيه هام: تم إيقاف جميع خدمات اتصالات
Header:
ادفع الآن
بسبب عدم سداد مبلغ $amount_due$ درهم المستحق على الحساب $account_number$ ضمن المهلة المحددة، تم إيقاف جميع خدماتك مؤقتاً.
قد يؤثر ذلك على سجلك الائتماني وعلى الاستفادة من خدمات اتصالات مستقبلاً.
يمكنك السداد الآن لإعادة تفعيل الخدمات.
CTA:
ادفع الآن
شكراً لك،
فريق اتصالات
```

<a id="b2c-ex-email-r006"></a>

#### B2C-EX-EMAIL-R006

Source: BANK / Email_Final / row 6. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject: Make your home smarter with the $New Neo Smart Home Plan$
Header: $5$ smart devices for just $AED 100 per month$

Dear <Customer>,

Explore our $New Neo Smart Home Plan$, the perfect add-on to your existing Home Plan for just AED $100$ per month.

As part of this plan, you get 5 smart devices:
1x Smart Camera or Doorbell to monitor your home from anywhere
1x Smart Lock Bundle to manage your home remotely
1x Smart Wall Switch to control your lights with ease
1x Echo Pop for voice controlling your smart home
1x IoT Hub for controlling all your smart devices
Ready to upgrade?

Visit $Link$ to make your home smarter, safer, and more connected. 
If you have any questions or need assistance, our customer service team is here for you anytime.

Thank you for choosing etisalat. We look forward to serving you.
```

**English after — source example**

```text
Subject: 
Make home smarter and safer with the $New Neo Smart Home Plan$

Header: 
5 upgrades. AED 100/month. That’s smart.

Body:
Hello <Customer>,

Discover the $New Neo Smart Home Plan$, the smart add-on that makes your home smarter and safer – for just AED 100/month.

Keep an eye on your home from anywhere, lock doors remotely, turn on lights with a tap, and manage everything with your phone – or your voice. 

Here’s what’s included with the plan:

1x Smart Camera or Doorbell
1x Smart Lock Bundle
1x Smart Wall Switch
1x Echo Pop (voice control hub)
1x IoT Hub

Ready to upgrade?

CTA: Upgrade now [$Link$]

Have questions? Contact support – available 24/7.

Discover a world of more with etisalat.

```

**Arabic — source example**

```text
Subject:
بيتك أذكى وأكثر أماناً مع $New Neo Smart Home Plan$
Header:
5 ترقيات بـ100 درهم شهرياً
مرحباً <Customer>،
اكتشف $New Neo Smart Home Plan$ — إضافة ذكية ترفع مستوى الأمان والراحة في منزلك، مقابل 100 درهم شهرياً فقط.
تابع منزلك من أي مكان، تحكّم في الأبواب والإضاءة وأكثر عن بُعد، بسهولة عبر هاتفك أو بالصوت.
تشمل الباقة:
كاميرا ذكية أو جرس باب ذكي (1)
حزمة القفل الذكي (1)
مفتاح حائط ذكي (1)
جهاز Echo Pop للتحكّم الصوتي (1)
جهاز IoT Hub (1)
جاهز للترقية؟
CTA:
قم بترقية باقتك الآن [$Link$]
فريق الدعم متوفر في خدمتكم على مدار الساعة لأي استفسار.
دايماً في أكثر مع اتصالات.

```

<a id="b2c-ex-email-r007"></a>

#### B2C-EX-EMAIL-R007

Source: BANK / Email_Final / row 7. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject: Your etisalat Device Protection Plan is Now Active

Dear $Customer Name$,

Congratulations on protecting your $Device Insured$ with etisalat Device Protection! Your coverage starts today ($Today's Date$), giving you peace of mind against unexpected damage for the next 2 years.

Your Policy
•        Policy Number: $Policy No.$
•        A full copy of your policy document will be sent to your registered email by Protect4Less, our authorised insurance partner who manages the full claims process.

Making a Claim
If you ever need to make a claim:
•        etisalat Customers: Submit your claim directly via the etisalat UAE app, under the $section1$ section.
•        Non-etisalat Customers: Submit your claim at www.protect4less.com.

Claims are typically processed within 24–48 hours, and you will be notified by email at every stage. For assistance regarding your claims, please contact customercare@protect4less.com, and for any other enquiries, please contact etisalat customer support.

Thank you for choosing etisalat Device Protection.

Best regards,
The etisalat Team
```

**English after — source example**

```text
Subject: 
Your etisalat device is now protected – enjoy peace of mind

Body:
Hello there,

Great news – your $Device Insured$ is now protected against accidental damage for the next two years with etisalat Device Protection. 

Here’s everything you need to know:

Your policy
- Policy number: $Policy No.$. 
- Start date: ($Today's Date$)
- End date: $TwoYearsFromToday:dd MMMM yyyy$ 

You’ll also get a full copy of your policy via email from Protect4Less, our authorised insurance partner.

Making a claim
- If you’re an etisalat customer, submit your claim in the etisalat UAE app, under $section1$ 
- If you're not an etisalat customer, submit your claim at www.protect4less.com
- Claims are typically processed within 24–48 hours

Have questions about a claim? Email customercare@protect4less.com

Have other questions? Contact etisalat support – available 24/7._x000B_

Welcome to a world of more.
```

**Arabic — source example**

```text
Subject:
تم تفعيل حماية جهازك من اتصالات
مرحباً،
تم تفعيل خدمة حماية الأجهزة من اتصالات لجهازك $Device Insured$، لتشمل الحماية من الأضرار العرضية لمدة عامين.
معلومات التغطية:
رقم الوثيقة: $Policy No.$
تاريخ ابتداء التغطية: ($Today's Date$)
تاريخ انتهاء التغطية: $TwoYearsFromToday:dd MMMM yyyy$
كما ستصلك نسخة كاملة من وثيقة التأمين عبر البريد الإلكتروني من Protect4Less، شريك اتصالات المعتمد.
في حال الحاجة إلى تقديم مطالبة:
يمكن لعملاء اتصالات تقديم المطالبة عبر تطبيق etisalat UAE، ضمن قسم $section1$
يمكن لغير عملاء اتصالات التقديم عبر الموقع:
www.protect4less.com
تتم مراجعة المطالبات خلال 24–48 ساعة عادةً
للاستفسار عن المطالبات، يمكن التواصل مباشرةً مع Protect4Less عبر:
customercare@protect4less.com
ولأي استفسارات أخرى، فريق دعم اتصالات متوفر في خدمتكم على مدار الساعة.
مع اتصالات، دايماً في أكثر.

```

<a id="b2c-ex-email-r008"></a>

#### B2C-EX-EMAIL-R008

Source: BANK / Email_Final / row 8. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Pay Your Bill Today
Account Number: < Acc>
DD, MM, YYYY
Don't Delay and Pay Now!
Dear Customer,
This is an important reminder that your account bill is due today. Please settle your bill today and continue enjoying your etisalat services.
Bill Details
Account Number: $account_number$
Amount Due: $amount_dues
Due Date: $due_Date$
Spend more time enjoying your etisalat services and let Autopay take care of your bill payments.
SET UP AUTOPAY
View & pay your bill easily on the etisalat UAE app
<Standard Footer>

```

**English after — source example**

```text
Subject:
Important: Your bill is due today

Header:
Make a payment today

Body:
Hello there,


Your bill for $amount_due$ on account $account_number$ is due today.

Pay now and continue to enjoy life on the UAE’s original mobile network. Or set up Autopay and never miss a payment.

CTA: Pay now

Thanks,

The etisalat Team

```

**Arabic — source example**

```text
Subject:
تنبيه هام: موعد سداد فاتورتك اليوم
Header:
سدّد اليوم لتفادي أي انقطاع
مرحباً،
نودّ تذكيرك بأن فاتورتك بقيمة $amount_due$ درهم على الحساب $account_number$ مستحقة اليوم.
يمكنك السداد الآن للاستمرار في استخدام والاستمتاع بخدمات اتصالات.
ولتفادي تفويت أي دفعة مستقبلاً، يمكنك أيضًا تفعيل الدفع التلقائي (Autopay).
CTA:
ادفع الآن
شكرًا لك،
فريق اتصالات
```

<a id="b2c-ex-email-r009"></a>

#### B2C-EX-EMAIL-R009

Source: BANK / Email_Final / row 9. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
Subject: Your $Parental Control $ subscription is confirmed 
HEADER: Enjoy $3 Months free_Offer$ + free installation

Dear <Customer>,

Thank you for subscribing to the $Parental Control$ Service! Your subscription has been successfully added to your account $[Account Number]$. Enjoy $3 months FREE$ until $Offer-expiry date$. After the free period, standard monthly charges will apply. 

To complete your installation, please book a technician visit here: $Book_Link$.
Note: Free installation is subject to the type of router you have. 
 
To learn how $Parental Control$ can help create a safer online space for your family, visit: $Link$.

If you have any questions or need assistance, our customer service team is here for you anytime.

Thank you for choosing etisalat. We look forward to serving you.
```

**English after — source example**

```text
Subject: 
Welcome to $Parental Control$

Header:
Keeping your family safe

Body:

Hello there,



Thanks for subscribing to etisalat’s $Parental Control$ service. We’ve now added it to your account: $[Account Number]$. 

And as a new subscriber, we’re giving you the first 3 months free. Plus, free installation for selected routers.
Because sometimes more is more.

Ready to book your installation?  

CTA: Book now: $Book_Link$. 
 


Learn more about how $Parental Control$ keeps your family safe: [$Link$]


Welcome to a world of more.
```

**Arabic — source example**

```text
Subject:
تم تفعيل خدمة الإشراف الأبوي
Header:
أمان عائلتك يبدأ من هنا
مرحباً،
تم تفعيل خدمة الإشراف الأبوي من اتصالات وإضافتها إلى حسابك
(رقم الحساب: $Account Number$).
وبمناسبة اشتراكك الجديد، يمكنك الاستمتاع بالأشهر الثلاثة الأولى مجاناً،
إلى جانب تركيب مجاني على أجهزة مختارة.
هل ترغب بتحديد موعد التركيب الآن؟
CTA:
احجز موعد التركيب: $Book_Link$
للاطلاع على تفاصيل الخدمة وكيف تساعدك على إدارة استخدام الإنترنت في المنزل:
$Link$
مع اتصالات، دايماً في أكثر.
```

<a id="b2c-ex-email-r010"></a>

#### B2C-EX-EMAIL-R010

Source: BANK / Email_Final / row 10. Parent: B2C-EMAIL-001.

**English before — comparison only**

```text
*No text supplied in this source cell.*
```

**English after — source example**

```text
Subject: 
Urgent: data and SMS roaming restrictions in Russia

Header:
What you need to know

Body:
Dear Customer,

Russia is now suspending data and SMS roaming services for 24 hours on arrival. Voice calls aren’t affected.

This is a mandatory suspension for all international users, which we weren’t informed about beforehand. 

Here’s what you need to know:

- When you first connect to a Russian network, your data and SMS will be suspended for 24 hours
- You can still make voice calls
- If you don’t use your SIM for 3 days after the suspension, Russia will apply a second 24-hour suspension 

What we recommend:

- Use Wi-Fi where possible
- Expect data and SMS outages during your stay
- Let friends and family know about the suspension before you travel
- Keep updated about restrictions in the etisalat UAE app  

Have questions? We’re on hand to help 24/7. 

CTA: Contact support

Thank you,

The etisalat team

```

**Arabic — source example**

```text
Subject:
تنبيه عاجل: قيود على التجوال (البيانات والرسائل) في روسيا
Header:
معلومات مهمة قبل وأثناء السفر
مرحباً،
طرأت تحديثات جديدة على خدمات التجوال في روسيا، بحيث يتم إيقاف خدمات البيانات والرسائل النصية مؤقتاً لمدة 24 ساعة عند الوصول.
المكالمات الصوتية غير متأثرة وتعمل كالمعتاد.
هذا الإجراء إلزامي ويُطبق على جميع المستخدمين الدوليين.
ما الذي يجب معرفته:
عند الاتصال بشبكة روسية للمرة الأولى، سيتم إيقاف البيانات والرسائل النصية لمدة 24 ساعة
يمكنك الاستمرار في إجراء واستقبال المكالمات الصوتية
في حال عدم استخدام شريحتك لمدة 3 أيام بعد انتهاء الإيقاف، قد يتم تطبيق إيقاف إضافي لمدة 24 ساعة
نوصي بما يلي:
استخدام شبكات Wi-Fi كلما أمكن
توقع انقطاع مؤقت في خدمات البيانات والرسائل خلال فترة إقامتك
إبلاغ العائلة أو الأصدقاء بهذه القيود قبل السفر
متابعة آخر التحديثات عبر تطبيق etisalat UAE
فريق الدعم متوفر في خدمتكم على مدار الساعة لأي استفسار.
CTA:
تواصل مع الدعم
شكراً لك،
فريق اتصالات

```

### BANK — Push Notification_Final

Channel dependency: B2C-PUSH-001. Populated examples: 6.

| Example ID | Source row | English-after preview |
| --- | --- | --- |
| [B2C-EX-PUSH-R002](#b2c-ex-push-r002) | 2 | Title: Your free welcome gift Short Description: Here’s your free welcome gift from the UAE’s original mobile… |
| [B2C-EX-PUSH-R003](#b2c-ex-push-r003) | 3 | Title: Your free gift is waiting Short Description: Want to talk more, watch more, or eat more? Claim today be… |
| [B2C-EX-PUSH-R004](#b2c-ex-push-r004) | 4 | Title: Your gift expires tonight Short Description: Hurry – your free welcome gift expires at midnight. Long D… |
| [B2C-EX-PUSH-R005](#b2c-ex-push-r005) | 5 | Title: Add-on payment coming up Short description: Add-on fees will be charged on <due date>. Manage them in t… |
| [B2C-EX-PUSH-R006](#b2c-ex-push-r006) | 6 | Title: Your add-on will renew Short Description: Renews on <date>. No action needed. Keep enjoying $add-on_nam… |
| [B2C-EX-PUSH-R007](#b2c-ex-push-r007) | 7 | Title Technical issue detected Short description Don’t worry – we’ll send a technician to fix it for free. Boo… |

<a id="b2c-ex-push-r002"></a>

#### B2C-EX-PUSH-R002

Source: BANK / Push Notification_Final / row 2. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
Title: Your plan is active. 
Short Description: Welcome to etisalat. A free welcome gift is ready for $ACCOUNT_NUMBER$.
Long Description: Get started on your new plan with something special. Choose a welcome gift like data, minutes, Careem Plus & more. You have <X> days to claim.  
CTA- Claim now
```

**English after — source example**

```text
Title: 
Your free welcome gift

Short Description: 
Here’s your free welcome gift from the UAE’s original mobile network.

Long Description: 
Choose from data to minutes and more. Claim your free gift within <X> days – it’s our way of saying thank you, and welcome to the UAE's original mobile network.

CTA: Claim now
```

**Arabic — source example**

```text
Title:
هديتك الترحيبية المجانية
Short Description:
إليك هدية ترحيبية من أول شبكة اتصالات في الإمارات
Long Description:
اختر هديتك الخاصة، واستفد من البيانات والدقائق المجانية وأكثر.
احصل عليها خلال <X> أيام — مرحباً بك وشكراً لانضمامك لأول شبكة اتصالات في الإمارات.
CTA:
اختر هديتك
```

<a id="b2c-ex-push-r003"></a>

#### B2C-EX-PUSH-R003

Source: BANK / Push Notification_Final / row 3. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
Title:  Claim your gift.  
Short Description: Hurry – You have <X> days left to claim your welcome gift for account $ACCOUNT_NUMBER$.
Long Description: Enjoy a free welcome gift. Choose from options like data, minutes or Careem Plus and enjoy uninterrupted services with etisalat. Don’t miss out – just <X> days left to claim. 
CTA – Claim now. 
```

**English after — source example**

```text
Title: 
Your free gift is waiting

Short Description: 
Want to talk more, watch more, or eat more? Claim today before it expires.

Long Description: 
Choose from data to minutes and more. Claim your free gift within <X> days – it’s our way of saying thank you, and welcome to the UAE's original mobile network.

CTA: Claim now
```

**Arabic — source example**

```text
Title:
هديتك بانتظارك..
Short Description:
مكالمات أكثر، مشاهدة أكثر، وحتى أكل أكثر — احصل عليها اليوم قبل انتهاء صلاحيتها.
Long Description:
اختر هديتك الخاصة، واستفد من البيانات والدقائق المجانية وأكثر.
احصل عليها خلال <X> أيام — مرحباً بك وشكراً لانضمامك لأول شبكة اتصالات في الإمارات.
CTA:
اختر هديتك
```

<a id="b2c-ex-push-r004"></a>

#### B2C-EX-PUSH-R004

Source: BANK / Push Notification_Final / row 4. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
Title: Your gift expires today.
Short Description: Your plan includes a free welcome gift – act now to make the most of your plan. 
Long Description: Today is your final chance to enjoy something extra with your new plan. Redeem your gift before it expires tonight and continue experiencing the best of etisalat. 
CTA – Claim now.
```

**English after — source example**

```text
Title: 
Your gift expires tonight

Short Description: 
Hurry – your free welcome gift expires at midnight.

Long Description: 
Your gift expires at midnight – don’t miss out on a world of more. Choose from data, minutes, or even Careem Plus. _x000B_

CTA: Claim now
```

**Arabic — source example**

```text
Title:
تنتهي صلاحية هديتك اليوم
Short Description:
ستنتهي صلاحية هديتك الترحيبية عند منتصف الليل.
Long Description:
ستنتهي صلاحية هديتك عند منتصف الليل. اختر من بين بيانات ودقائق مجانية وحتى اشتراك في Careem Plus. مع اتصالات، دايماً في أكثر.
CTA:
اختر هديتك
```

<a id="b2c-ex-push-r005"></a>

#### B2C-EX-PUSH-R005

Source: BANK / Push Notification_Final / row 5. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
Title: Add-on charges due soon
Short Description: Friendly reminder that your add-on fees will be deducted soon. View and manage your add-ons and keep enjoying the services.
Long Description: Your add-on fees will be deducted from your account shortly. For uninterrupted service click below to manage your add-ons.
CTA: Manage Add-ons
```

**English after — source example**

```text
Title: 
Add-on payment coming up 

Short description: 
Add-on fees will be charged on <due date>. Manage them in the etisalat UAE app.

Long description:  
Not enough credit in your account? Recharge in a few clicks in the etisalat UAE app.

CTA: Visit the app
```

**Arabic — source example**

```text
Title:
خصم رسوم الميزة الإضافية
Short Description:
تُخصم رسوم الميزة الإضافية في <due date>. يمكنك إدارتها عبر تطبيق etisalat UAE.
Long Description:
رصيدك غير كافِ؟
يمكنك إعادة تعبئة الرصيد بخطوات بسيطة عبر تطبيق etisalat UAE
CTA:
افتح التطبيق
```

<a id="b2c-ex-push-r006"></a>

#### B2C-EX-PUSH-R006

Source: BANK / Push Notification_Final / row 6. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
Title: Manage Auto-Renew Add-Ons
Short Description: Friendly reminder, you have an auto renewing Add-on, take a moment to review your add-ons at your convenience.
Long Description: Your $add-on_name$ will be auto-renewal soon. To view and manage your add-ons for the upcoming month click below.
CTA: Manage Add-ons 
```

**English after — source example**

```text
Title: 
Your add-on will renew

Short Description: 
Renews on <date>. No action needed. Keep enjoying $add-on_name$.
Long description: Manage your add-ons in the etisalat UAE app.
```

**Arabic — source example**

```text
Title:
تجديد ميزتك تلقائيًا
Short Description:
تتجدد ميزتك في <date>. لا يلزمك أي إجراء للاستمتاع بـ$add-on_name$.
الوصف الطويل: يمكنك إدارة ميزاتك الإضافية عبر تطبيق etisalat UAE.
```

<a id="b2c-ex-push-r007"></a>

#### B2C-EX-PUSH-R007

Source: BANK / Push Notification_Final / row 7. Parent: B2C-PUSH-001.

**English before — comparison only**

```text
*No text supplied in this source cell.*
```

**English after — source example**

```text
Title
Technical issue detected

Short description
Don’t worry – we’ll send a technician to fix it for free. Book a time that works for you.
CTA: Book a visit
CTA destination: &LINK& (destination only; do not display this token in the short description)
```

**Arabic — source example**

```text
Title:
تم رصد خلل تقني في خدمتك
Short Description:
لا داعي للقلق، سنرسل فنيًا لإصلاح الخلل مجانًا. حدّد الموعد المناسب لك.
الإجراء: احجز الموعد
وجهة الإجراء: &LINK& (وجهة الرابط فقط؛ لا يُعرض هذا الرمز في الوصف القصير)
```
