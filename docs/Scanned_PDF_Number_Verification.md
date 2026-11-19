# Scanned PDF numeric verification

Native text PDFs keep their normal extraction path. Scanned pages are transcribed with no writing or summarisation instructions. The independent verifier sees only a single source image, never the proposed transcription. It returns heading/body source lines rather than manually enumerating numeric totals. Local code extracts and compares numeric occurrence counts, including repeated values, signs, dates, technical identifiers and section labels.

Two ordinary reads and up to two verifier attempts share a page deadline. A failed page still rejects the entire document rather than silently omitting source facts. Experimental higher-resolution, regional and reasoning retries did not resolve the supplied page reliably and are not enabled in the application flow.

Optional `DOCLING_OCR_LANGUAGES` (comma-separated, such as `ar,en`) and `DOCLING_OCR_PRESET` select languages and a service-provided engine. Omission preserves existing service defaults. These options cannot install missing OCR models or repair a remote service. Confirm language/engine availability with the service administrator before enabling them. Current scanned-PDF routing still uses the guarded AI reader; adding these settings does not bypass numeric checks or make Docling the primary scan path.

## Page 4 diagnostic result, 30 October 2026

Only the user-approved page 4 was tested externally. AI source-only reads disagreed on Arabic dotted reference labels and repeated digits. Docling health returned HTTP 200; its default conversion returned almost no Arabic. Conversions requesting Arabic and English failed with `Internal processing error`, including explicit `easyocr` and `tesseract` presets. The service logs are needed to establish the exact engine/language failure. A missing Arabic model is possible but not proven by that generic service response. The file has not passed end-to-end upload verification.

The same configured gateway, confidentiality restrictions, model token limits and request-rate controls continue to apply. Confidential documents never acquire a cloud fallback. No new OCR service or external storage is introduced.

Original PDFs and instructions are not changed. Numeric agreement is a cross-check, not a guarantee that OCR transcribes every word correctly. Users should review extracted source text, especially legal and technical documents.
