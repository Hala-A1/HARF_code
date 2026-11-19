import json
import unittest
from unittest.mock import patch

from ai_service import analyze_copy
from quality_analysis import component_length_checks, evidence_context, excerpt, literal_checks, normalize_review, source_inventory


class QualityAnalysisTests(unittest.TestCase):
    def setUp(self):
        from assessment_cache import SOURCE_FACTS, OUTPUT_REVIEWS
        SOURCE_FACTS.clear()
        OUTPUT_REVIEWS.clear()
        self.sources = {"G1-S1": {"id": "G1-S1", "filename": "system.md", "section": "Tone > Clarity",
                                 "line": 4, "end_line": 8, "version": "abc123", "text": "Use short, clear sentences. Preserve prices and dates."}}

    def check(self, **updates):
        return {"rule": "Clear sentences", "category": "clarity", "status": "met", "detail": "Short wording",
                "output_quote": "Hello", "references": [{"source_id": "G1-S1", "rule_quote": "Use short, clear sentences."}], **updates}

    def review(self, **updates):
        return normalize_review({"checks": [self.check()], **updates}, self.sources, "Hello", "Hello")

    def test_score_is_calculated_and_citations_have_real_file_sections(self):
        result = self.review(score=19)
        self.assertEqual(result["score"], 100)
        citation = result["checks"][0]["references"][0]
        self.assertEqual(citation["filename"], "system.md")
        self.assertEqual(citation["section"], "Tone > Clarity")
        self.assertEqual(citation["line"], 4)
        self.assertNotIn("text", citation)

    def test_fabricated_citation_or_quote_cannot_receive_credit(self):
        for refs in [[{"source_id": "invented", "rule_quote": "Use short, clear sentences."}],
                     [{"source_id": "G1-S1", "rule_quote": "Every greeting scores 92%."}]]:
            result = self.review(checks=[self.check(references=refs)])
            self.assertIsNone(result["score"])
            self.assertEqual(result["checks"][0]["status"], "unverified")
            self.assertFalse(result["checks"][0]["references"])

    def test_fabricated_output_evidence_cannot_pass(self):
        result = self.review(checks=[self.check(output_quote="Output that does not exist")])
        self.assertIsNone(result["score"])
        self.assertEqual(result["checks"][0]["output_quote"], "")

    def test_section_id_citations_use_actual_server_text(self):
        result = self.review(checks=[self.check(references=[{"source_id": "G1-S1"}])])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["checks"][0]["references"][0]["rule_quote"], self.sources["G1-S1"]["text"])

    def test_weighted_checks_exclude_not_applicable_and_deduplicate(self):
        result = self.review(checks=[self.check(), self.check(), self.check(rule="Price", category="claims", status="missing"), self.check(rule="CTA", status="not_applicable")])
        self.assertEqual(result["score"], 25)
        self.assertEqual(len(result["checks"]), 3)

    def test_changed_price_caps_style_score_and_shows_before_after_evidence(self):
        result = normalize_review({"checks": [self.check(output_quote="AED 150")], "facts": [
            {"fact": "Price", "input_quote": "AED 100", "output_quote": "AED 150", "status": "changed", "detail": "Price changed"}]},
            self.sources, "Price AED 100", "Hello AED 150")
        self.assertEqual(result["score"], 69)
        self.assertEqual(result["source_preservation"], 0)
        self.assertEqual(result["facts"][0]["input_quote"], "AED 100")

    def test_arabic_translation_preserves_meaning_despite_low_word_overlap(self):
        result = normalize_review({"checks": [self.check(output_quote="السعر")], "facts": [
            {"fact": "Price", "input_quote": "AED 100", "output_quote": "١٠٠ درهم", "status": "preserved"}]},
            self.sources, "The price is AED 100", "السعر ١٠٠ درهم")
        self.assertEqual(result["source_preservation"], 100)
        self.assertEqual(result["wording_similarity"], 0)
        self.assertTrue(result["literal_checks"][0]["found"])

    def test_missing_and_uncertain_facts_do_not_count_as_preserved(self):
        result = normalize_review({"checks": [], "facts": [
            {"fact": "Deadline", "input_quote": "Friday", "status": "missing"},
            {"fact": "Price", "input_quote": "AED 100", "output_quote": "invented quote", "status": "preserved"},
            {"fact": "Invented source", "input_quote": "not in source", "status": "preserved"}]},
            self.sources, "AED 100 until Friday", "Hello")
        self.assertEqual(len(result["facts"]), 2)
        self.assertEqual(result["source_preservation"], 0)
        self.assertEqual(result["facts"][1]["status"], "uncertain")

    def test_no_input_does_not_claim_preservation(self):
        result = normalize_review({"checks": [self.check()]}, self.sources, "", "Hello")
        self.assertIsNone(result["source_preservation"])
        self.assertIsNone(result["wording_similarity"])
        self.assertEqual(source_inventory({"facts": []}, "Hello"), [])

    def test_unsupported_additions_only_show_existing_output_quotes(self):
        result = self.review(unsupported_claims=[{"output_quote": "Hello", "detail": "Possible addition"}, {"output_quote": "invented", "detail": "Ignore"}])
        self.assertEqual(result["score"], 69)
        self.assertEqual(len(result["unsupported_claims"]), 1)

    def test_large_document_scope_is_explicit(self):
        original = "a" * 61000
        result = normalize_review({"checks": []}, self.sources, original, "Hello")
        self.assertTrue(result["scope"]["partial"])
        self.assertIn("partial source review", excerpt(original, 60000))

    def test_literals_normalize_arabic_digits_thousands_and_percent(self):
        values = literal_checks("AED 1,000.50, save 25%, https://example.com/offer", "١٬٠٠٠٫٥٠ درهم و٢٥٪")
        self.assertTrue(values[0]["found"])
        self.assertTrue(values[1]["found"])
        self.assertFalse(values[2]["found"])

    def test_guidelines_are_channel_scoped_and_specific(self):
        for channel in ["b2c", "security"]:
            text, sources = evidence_context(channel, "SMS" if channel == "b2c" else "Compliance memo", "Template 1" if channel == "security" else "SMS")
            self.assertTrue(sources)
            self.assertNotIn("B2B_WEBSITE", text)
            self.assertTrue(all(("REGULATORY_COMPLIANCE" if channel == "security" else channel.upper()) in source["filename"].upper() for source in sources.values()))
        text, sources = evidence_context("b2b", "Google Paid Search", "Business Internet offer")
        self.assertIn("04_GOOGLE_PAID_SEARCH", text)
        self.assertFalse(any(source["filename"] == "03_WEBSITE_COMPONENT_SCHEMA.md" for source in sources.values()))

    def test_analyzer_supplies_requirements_and_never_trusts_model_percentage(self):
        with patch("quality_analysis.evidence_context", return_value=("[G1-S1] Use short, clear sentences.", self.sources)), patch("ai_service._run_completion", side_effect=[json.dumps({"facts": [{"fact": "Greeting", "input_quote": "Hello"}]}), json.dumps({"score": 92, "checks": [self.check()], "facts": [{"fact_id": "F1", "status": "preserved", "output_quote": "Hello"}]})]) as complete:
            result = analyze_copy("Hello", "Hello", "b2c", "SMS", "Neutral greeting", "improve", "en")
        self.assertEqual(result["score"], 100)
        payload = json.loads(complete.call_args.args[1])
        self.assertEqual(payload["user_requirements"], "Neutral greeting")
        self.assertEqual(payload["output_language"], "en")

    def test_every_independently_identified_fact_remains_in_comparison(self):
        inventory = source_inventory({"facts": [{"fact": "Automatic backup", "input_quote": "Automatic daily backup"}, {"fact": "Daily frequency", "input_quote": "Automatic daily backup"}]}, "Automatic daily backup")
        result = normalize_review({"checks": [self.check()], "facts": [{"fact_id": "F2", "status": "preserved", "output_quote": "Daily backup"}]}, self.sources, "Automatic daily backup", "Hello. Daily backup", inventory=inventory)
        self.assertEqual(len(result["facts"]), 2)
        self.assertEqual(result["facts"][0]["status"], "uncertain")
        self.assertEqual(result["source_preservation"], 50)

    def test_source_inventory_rejects_facts_without_real_input_quotes(self):
        with self.assertRaises(ValueError):
            source_inventory({"facts": [{"fact": "Invented price", "input_quote": "AED 500"}]}, "No price supplied")

    def test_reference_notes_do_not_prove_facts_in_customer_copy(self):
        output = "[COPY READY CONTENT]\nTitle: Cloud backup\n\n[REFERENCE AND VALIDATION]\nSource facts: Automatic daily backup"
        result = normalize_review({"checks": [], "facts": [{"fact": "Automatic backup", "input_quote": "Automatic daily backup", "output_quote": "Automatic daily backup", "status": "preserved"}]}, self.sources, "Automatic daily backup", output)
        self.assertEqual(result["facts"][0]["status"], "uncertain")
        self.assertEqual(result["source_preservation"], 0)
        self.assertEqual(result["facts"][0]["output_quote"], "")

    def test_component_lengths_are_counted_independently_of_claimed_pass(self):
        _, sources = evidence_context("b2b", "Website", "Component 1")
        output = "[COPY READY CONTENT]\nComponent: Component 1\nTitle: Business Cloud Backup\nSub-title: Daily backups\n\n[REFERENCE AND VALIDATION]\nTitle: 20/20 PASS"
        checks = component_length_checks(output, "Daily backups", "Component 1", "b2b", sources)
        title = next(item for item in checks if item["rule"].startswith("Title:"))
        self.assertEqual(title["status"], "missing")
        self.assertIn("21 / 20", title["detail"])
        self.assertEqual(title["references"][0]["source_id"] in sources, True)


if __name__ == "__main__":
    unittest.main()
