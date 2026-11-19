import io
import json
import os
import unittest
import copy
from pathlib import Path
import tempfile
import access_control
from unittest.mock import patch

from fastapi.testclient import TestClient

import ai_service
from main import app


class CopywriterIntegrationTests(unittest.TestCase):
    def test_super_admin_can_generate_bilingual_copy_and_access_format_options(self):
        headers = {'X-User-Email': 'developer@eand.ae'}
        with patch('copywriter.enhance_feedback', return_value='Own generated text') as single:
            response = self.client.post('/api/enhance', headers=headers, json={'feedback':'Own brief','team_channel':'b2b','task':'improve'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['enhanced'], 'Own generated text')
            single.assert_called_once()
        with patch('copywriter.enhance_bilingual_feedback', return_value={'english':'Own copy','arabic':'نصي'}) as bilingual:
            response = self.client.post('/api/enhance/bilingual', headers=headers, json={'feedback':'Own brief','team_channel':'b2b'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['arabic'], 'نصي')
            bilingual.assert_called_once()
        self.assertEqual(self.client.get('/api/output-options?team_channel=b2b',headers=headers).status_code,200)

    def test_obsolete_reference_endpoints_are_removed(self):
        self.assertEqual(self.client.get("/api/guidelines").status_code, 404)
        self.assertEqual(self.client.put("/api/guidelines", json={"content": "Not used"}).status_code, 404)
        self.assertEqual(self.client.post("/api/rewrite-weak", json={"generated": "Not used"}).status_code, 404)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data_file = Path(directory.name) / 'access.json'
        data_file.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        isolated = patch.object(access_control, 'DATA_FILE', data_file)
        isolated.start()
        self.addCleanup(isolated.stop)
        # API unit tests must not add sample entries to the application's activity history.
        activity = patch('copywriter.track')
        activity.start()
        self.addCleanup(activity.stop)
        self.client = TestClient(app, headers={"X-User-Email": "b2b.admin@eand.ae"})

    def test_copywriter_and_streaming_routes_coexist(self):
        with patch("copywriter.enhance_feedback", return_value="Clear copy") as enhance:
            for task in ("write", "improve", "review", "translate"):
                response = self.client.post("/api/enhance", json={
                    "feedback": "A brief", "task": task,
                    "channel": "SMS", "audience": "Youth",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["enhanced"], "Clear copy")
                enhance.assert_called_with("A brief", task, "SMS", "Youth", "b2b", "", "en")
        response = self.client.post("/api/generate", json={"prompt": ""})
        self.assertEqual(response.status_code, 404)

    def test_bilingual_generation_returns_both_languages_from_one_request(self):
        with patch("copywriter.enhance_bilingual_feedback", return_value={"english": "Clear copy", "arabic": "نص واضح"}) as bilingual:
            response = self.client.post("/api/enhance/bilingual", json={
                "feedback": "A brief", "task": "write", "channel": "SMS", "audience": "Youth",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"english": "Clear copy", "arabic": "نص واضح"})
        bilingual.assert_called_once_with("A brief", "write", "SMS", "Youth", "b2b", "")

    def test_bilingual_generation_parses_and_requires_both_outputs(self):
        with patch("ai_service.get_client") as client, patch("ai_service.get_model", return_value="copy-model"), patch("ai_service.guidelines_for_text", return_value="Brand glossary"):
            create = client.return_value.chat.completions.create
            create.return_value.choices = [unittest.mock.MagicMock(message=unittest.mock.MagicMock(content='{"english":"Clear copy","arabic":"نص واضح"}'))]
            self.assertEqual(ai_service.enhance_bilingual_feedback("Brief"), {"english": "Clear copy", "arabic": "نص واضح"})
            instructions = create.call_args.kwargs["messages"][0]["content"]
            self.assertIn('"english": "complete English copy"', instructions)
            self.assertIn('"arabic": "complete Arabic copy"', instructions)
            create.return_value.choices = [unittest.mock.MagicMock(message=unittest.mock.MagicMock(content='{"english":"Only English","arabic":""}'))]
            with self.assertRaises(ValueError):
                ai_service.enhance_bilingual_feedback("Brief")

    def test_channel_brain_is_used_by_both_languages(self):
        with patch("ai_service.instruction_text_for", return_value="Initial rules"):
            self.assertIn("Initial rules", ai_service.build_task_prompt("Hello"))
            for text in ("Hello", "مرحبا"):
                self.assertIn("Initial rules", ai_service.build_task_prompt(text))

    def test_specific_instructions_and_arabic_quality_rules_are_applied(self):
        prompt = ai_service.build_task_prompt(
            "Product brief", "write", "Website", "Business", "b2b",
            "Use the approved launch date and one short CTA.", "ar",
        )
        self.assertIn("Additional generation details supplied by the user", prompt)
        self.assertIn("Use the approved launch date and one short CTA.", prompt)
        self.assertIn("Modern Standard Arabic", prompt)
        self.assertIn("Translate the entire response into Arabic", prompt)
        self.assertIn("[المحتوى الجاهز للنسخ]", prompt)
        self.assertIn("Ready-to-send standard", prompt)
        self.assertIn("spelling and grammar check", ai_service.translation_instructions("Hello", "ar"))
        self.assertIn("ready-to-send", ai_service.translation_instructions("Hello", "ar"))

    def test_website_component_number_focuses_generation_on_markdown_schema(self):
        prompt = ai_service.build_task_prompt(
            "Create benefits copy for our managed cloud service.",
            "write", "Other", "Business", "b2b",
            "Use Component 13 with the supplied icon and a short benefits description.", "en",
        )
        self.assertIn("Website Component Library", prompt)
        self.assertIn("Component 13 — Benefits Component", prompt)
        self.assertIn("Component 13 is the only permitted component", prompt)
        self.assertIn("Title: mandatory, max 25 characters", prompt)
        self.assertIn("[COPY READY CONTENT]", prompt)
        self.assertIn("[REFERENCE AND VALIDATION]", prompt)
        self.assertIn("Do not use a Markdown table", prompt)
        self.assertIn("Never mark an over-limit", prompt)

    def test_website_component_can_be_inferred_from_distinctive_details(self):
        selected = ai_service.detect_website_component(
            "Build a plan card with the plan name, AED monthly price, six USPs, contract period and Buy Now CTA."
        )
        self.assertEqual(selected["number"], 5)
        selected = ai_service.detect_website_component(
            "Image mandatory. Heading max 40. Description max 215. CTA optional."
        )
        self.assertEqual(selected["number"], 17)

    def test_ambiguous_website_request_requires_component_resolution(self):
        prompt = ai_service.build_task_prompt(
            "Create website copy for our new business service.", "write", "Website", "Business",
        )
        self.assertIn("Resolve the requested website component before writing", prompt)
        self.assertIn("REQUIRED INPUT: website component type", prompt)

    def test_added_component_numbers_are_resolved_from_channel_schema(self):
        with patch('ai_service.website_component_blocks', return_value={42: '### Component 42 — Custom banner'}):
            self.assertEqual(ai_service.detect_website_component('Selected output: Component 42', 'b2b')['number'], 42)
            self.assertIsNone(ai_service.detect_website_component('Component 18', 'b2b'))

    def test_context_detection_forces_website_for_known_component(self):
        model_output = json.dumps({
            "channel": "Other", "audience": "Business", "channel_confidence": 20,
            "audience_confidence": 90, "reason": "Short brief",
        })
        with patch("ai_service._run_completion", return_value=model_output) as completion, patch("ai_service.guidelines_for_text", side_effect=AssertionError("Classification must not load writing guides")):
            context = ai_service.detect_copy_context("Create Component 2 intro copy for a business service.")
        self.assertLess(len(completion.call_args.args[0]), 4000)
        self.assertEqual(completion.call_args.kwargs["timeout"], 8)
        self.assertEqual(context["product_type"], "Unknown")
        self.assertEqual(context["channel"], "Website")
        self.assertGreaterEqual(context["channel_confidence"], 95)
        self.assertIn("Component 2", context["reason"])

    def test_targeted_revision_keeps_the_selected_component_schema(self):
        prompt = ai_service.build_task_prompt(
            "Component 10 — CTA Banner\nTitle: Connect business\nDescription: Grow with us",
            "improve", "Website", "Business", "b2b", "Keep the CTA concise.", "en",
        )
        self.assertIn("Component 10 — CTA Banner", prompt)
        self.assertIn("Title: mandatory, max 45 characters", prompt)
        self.assertIn("Component 10 is the only permitted component", prompt)

    def test_component_generation_repairs_over_limit_fields_before_return(self):
        component = ai_service.detect_website_component("Use Component 13")
        invalid = """[COPY READY CONTENT]
Component: Component 13 — Benefits Component
Icon: Supplied separately
Title: Secure cloud backup
Description: {description}

[REFERENCE AND VALIDATION]
Purpose: Explain the benefit.
Character counts:
- Title: 19/25 — PASS
- Description: 90/80 — FAIL
Source facts:
- Daily backup
Requirements:
- Icon: Supplied separately
Overall validation: FAIL""".format(description="A" * 90)
        valid = json.dumps({'fields': [{'id': 'field-2', 'alternatives': ['Daily backup with fast restore and 24/7 support.']}]})
        with patch("ai_service._run_completion", side_effect=[invalid, valid]) as completion:
            output = ai_service._component_validated_completion("Instructions", "Brief", component)
        self.assertEqual(completion.call_count, 2)
        self.assertFalse(ai_service._component_limit_issues(output, component))
        self.assertIn("Overall validation: PASS", output)

    def test_arabic_component_generation_localises_structure_and_source_facts(self):
        component = ai_service.detect_website_component("Use Component 4")
        invalid = """[COPY READY CONTENT]
Component: Component 4 — USP Featured
Title: Business Cloud Backup
Sub-title: نسخ احتياطي يومي تلقائي مع استعادة سريعة للملفات

[REFERENCE AND VALIDATION]
Purpose: إبراز القيمة الأساسية للخدمة.
Character counts:
- Title: 21/20 — FAIL
- Sub-title: 54/65 — PASS
Source facts:
- Automatically backs up business files every day
- Helps customers restore files quickly
Requirements:
- Icon: Supplied separately
Overall validation: FAIL"""
        valid = """[المحتوى الجاهز للنسخ]
المكوّن: المكوّن 4 — إبراز الميزة
الأيقونة: سيتم توفيرها بشكل منفصل
العنوان: نسخ سحابي آمن
العنوان الفرعي: نسخ احتياطي يومي واستعادة سريعة للملفات

[المرجع والتحقق]
الغرض: إبراز القيمة الأساسية للخدمة.
عدد الأحرف:
- العنوان: 14/20 — مطابق
- العنوان الفرعي: 45/65 — مطابق
الحقائق المصدرية:
- نسخ ملفات الأعمال احتياطياً كل يوم تلقائياً
- استعادة ملفات العملاء بسرعة
المتطلبات:
- الأيقونة: سيتم توفيرها بشكل منفصل
التحقق العام: مطابق"""
        with patch("ai_service._run_completion", return_value=valid) as completion:
            output = ai_service._component_validated_completion(
                "Instructions", "Brief", component, invalid, "ar",
            )
        self.assertEqual(completion.call_count, 1)
        self.assertFalse(ai_service._arabic_localization_issues(output))
        self.assertIn("[المحتوى الجاهز للنسخ]", output)
        self.assertIn("- نسخ ملفات الأعمال احتياطياً كل يوم تلقائياً", output)
        self.assertNotIn("Source facts:", output)
        mixed_component_name = output.replace("المكوّن 4 — إبراز الميزة", "Component 4 — USP Featured")
        self.assertTrue(ai_service._arabic_localization_issues(mixed_component_name))

    def test_document_extraction_and_upload_validation(self):
        response = self.client.post("/api/extract-upload", files={"file": ("brief.txt", "Hello مرحبا".encode(), "text/plain")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Hello مرحبا")
        self.assertEqual(self.client.post("/api/extract-upload", files={"file": ("bad.bin", b"bad", "application/octet-stream")}).status_code, 422)
        with patch("copywriter.extract_uploaded_content") as extract:
            response = self.client.post("/api/extract-upload", files={"file": ("large.txt", b"a" * (10 * 1024 * 1024 + 1), "text/plain")})
            self.assertEqual(response.status_code, 413)
            extract.assert_not_called()
        from docx import Document
        document = Document()
        document.add_paragraph("Product brief")
        data = io.BytesIO()
        document.save(data)
        self.assertEqual(ai_service.extract_uploaded_content("brief.docx", "", data.getvalue()), "Product brief")

    def test_context_analysis_and_rewrite_contracts(self):
        cases = [
            ("/api/detect-context", "detect_copy_context", {"feedback": "Hello"}, {"channel": "SMS", "audience": "Unknown"}),
            ("/api/analyze", "analyze_copy", {"generated": "Hello"}, {"score": 95, "findings": []}),
        ]
        for endpoint, function, payload, result in cases:
            with patch(f"copywriter.{function}", return_value=result):
                response = self.client.post(endpoint, json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"rewritten": result} if isinstance(result, str) else result)
            with patch(f"copywriter.{function}", side_effect=RuntimeError("upstream failure")):
                failed_response = self.client.post(endpoint, json=payload)
                if endpoint == "/api/detect-context":
                    self.assertEqual(failed_response.status_code, 200)
                    self.assertEqual(failed_response.json()["channel"], "Other")
                    self.assertEqual(failed_response.json()["channel_confidence"], 0)
                else:
                    self.assertEqual(failed_response.status_code, 502)

    def test_context_failure_preserves_local_component_detection(self):
        with patch("copywriter.detect_copy_context", side_effect=RuntimeError("upstream failure")):
            response = self.client.post("/api/detect-context", json={
                "feedback": "Create copy for the new service.",
                "instructions": "Use Component 13 with an icon, title and benefits description.",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["channel"], "Website")
        self.assertEqual(response.json()["channel_confidence"], 100)

    def test_missing_copy_model_returns_a_safe_error(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_MODEL": "", "COPYWRITER_AZURE_OPENAI_MODEL": "", "MODEL_PROVIDER": ""}), patch("ai_service.dotenv_values", return_value={}):
            response = self.client.post("/api/enhance", json={"feedback": "Hello"})
            self.assertEqual(response.status_code, 502)
            self.assertEqual(self.client.post("/api/generate", json={"prompt": ""}).status_code, 404)

    def test_translation_languages_validation_and_failure(self):
        with patch("copywriter.translate_copy", return_value="Translated copy") as translate:
            for language in ("en", "ar"):
                response = self.client.post("/api/translate", json={"generated": "Current result", "language": language})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"translated": "Translated copy"})
                translate.assert_called_with("Current result", language, "b2b")
            translate.reset_mock()
            for payload in ({"generated": "Text", "language": "fr"}, {"generated": "", "language": "en"}, {"generated": "  ", "language": "ar"}):
                self.assertEqual(self.client.post("/api/translate", json=payload).status_code, 422)
            translate.assert_not_called()
        with patch("copywriter.translate_copy", side_effect=RuntimeError("upstream failure")):
            self.assertEqual(self.client.post("/api/translate", json={"generated": "Text", "language": "en"}).status_code, 502)

    def test_word_export_preserves_bilingual_copy_and_direction(self):
        from docx import Document
        from docx.oxml.ns import qn
        sections = [
            {"language": "en", "text": "Offer <details> & pricing\nAED 100\n\nhttps://example.com"},
            {"language": "ar", "text": "مرحباً بكم\nالسعر 100 درهم"},
        ]
        with patch("copywriter.enhance_feedback") as enhance, patch("copywriter.translate_copy") as translate:
            response = self.client.post("/api/export/docx", json={"sections": sections})
            self.assertEqual(response.status_code, 200)
            self.assertIn("wordprocessingml.document", response.headers["content-type"])
            self.assertIn("generated-copy.docx", response.headers["content-disposition"])
            document = Document(io.BytesIO(response.content))
            self.assertEqual(len(document.inline_shapes), 1)
            self.assertEqual(document.paragraphs[0].alignment, 0)
            self.assertEqual([p.text for p in document.paragraphs], [
                "", "Score: Not evaluated", "Offer <details> & pricing", "AED 100", "https://example.com",
                "", "Score: Not evaluated", "مرحباً بكم", "السعر 100 درهم",
            ])
            self.assertIsNotNone(document.paragraphs[-1]._p.pPr.find(qn("w:bidi")))
            enhance.assert_not_called()
            translate.assert_not_called()

    def test_word_export_validation_and_errors(self):
        for sections in ([], [{"text": " "}], [{"text": "Text", "language": "fr"}], [{"text": "Text"}] * 3):
            self.assertEqual(self.client.post("/api/export/docx", json={"sections": sections}).status_code, 422)
        with patch("copywriter.create_copy_document", side_effect=ValueError("Invalid document")):
            self.assertEqual(self.client.post("/api/export/docx", json={"sections": [{"text": "Copy"}]}).status_code, 500)

    def test_translation_uses_explicit_target_and_rejects_empty_output(self):
        with patch("ai_service.get_client") as client, patch("ai_service.get_model", return_value="copy-model"), patch("ai_service.guidelines_for_text", return_value="Brand glossary"):
            create = client.return_value.chat.completions.create
            create.return_value.choices = [unittest.mock.MagicMock(message=unittest.mock.MagicMock(content="Translated copy"))]
            for language, target in (("en", "English"), ("ar", "Arabic")):
                self.assertEqual(ai_service.translate_copy("Original result", language), "Translated copy")
                self.assertIn(f"into {target} only", create.call_args.kwargs["messages"][0]["content"])
                self.assertIn("Brand glossary", create.call_args.kwargs["messages"][0]["content"])
                self.assertEqual(create.call_args.kwargs["messages"][1]["content"], "Original result")
            create.return_value.choices = [unittest.mock.MagicMock(message=unittest.mock.MagicMock(content=" "))]
            with self.assertRaises(ValueError):
                ai_service.translate_copy("Original result", "ar")

    def test_copywriter_uses_its_own_deployment_without_changing_poster_settings(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "poster-key", "AZURE_OPENAI_ENDPOINT": "https://poster.invalid", "COPYWRITER_AZURE_OPENAI_API_KEY": "copy-key", "COPYWRITER_AZURE_OPENAI_ENDPOINT": "https://copy.invalid", "COPYWRITER_AZURE_OPENAI_MODEL": "copy-model", "MODEL_PROVIDER": ""}), patch("ai_service.dotenv_values", return_value={"AZURE_OPENAI_API_KEY": "copy-key", "AZURE_OPENAI_ENDPOINT": "https://copy.invalid", "AZURE_OPENAI_MODEL": "copy-model"}), patch("ai_service.AzureOpenAI") as client:
            ai_service.get_client()
            from llm_rate_limits import RateLimitedHttpClient
            http_client = client.call_args.kwargs['http_client']
            self.assertIsInstance(http_client, RateLimitedHttpClient)
            client.assert_called_once_with(api_key="copy-key", azure_endpoint="https://copy.invalid", api_version="2024-10-21", timeout=90.0, max_retries=1, http_client=http_client)
            http_client.close()
            self.assertEqual(ai_service.get_model(), "copy-model")
            self.assertEqual(os.environ["AZURE_OPENAI_API_KEY"], "poster-key")


if __name__ == "__main__":
    unittest.main()
