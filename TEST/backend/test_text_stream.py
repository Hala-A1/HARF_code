import json
import unittest
import copy
from pathlib import Path
import tempfile
import access_control
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app
import ai_service
from stream_errors import StreamFailure, stream_error_details


def chunk(content=None, finish_reason=None):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content), finish_reason=finish_reason)])


class TextStreamTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data_file = Path(directory.name) / 'access.json'
        data_file.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        isolated = patch.object(access_control, 'DATA_FILE', data_file)
        isolated.start()
        self.addCleanup(isolated.stop)
        activity = patch('copywriter.track')
        activity.start()
        self.addCleanup(activity.stop)

    def test_transient_and_permanent_errors_are_distinguished(self):
        from openai import APIConnectionError
        import httpx
        error = APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
        self.assertEqual(stream_error_details(error)["code"], "connection_error")
        self.assertTrue(stream_error_details(error)["retryable"])
        for code in ["content_filter", "max_output_tokens", "configuration"]:
            details = stream_error_details(StreamFailure(code))
            self.assertEqual(details["code"], code)
            self.assertFalse(details["retryable"])

    def test_routes_forward_deltas_and_complete(self):
        client = TestClient(app, headers={"X-User-Email": "b2b.admin@eand.ae"})
        cases = [
            ("enhance", "stream_enhance_feedback", {"feedback": "Brief"}),
            ("translate", "stream_translate_copy", {"generated": "Hello", "language": "ar"}),
        ]
        for route, function, payload in cases:
            with patch(f"copywriter.{function}", side_effect=lambda *args: (chunk for chunk in ["Hello\n", "مرحبا"])):
                response = client.post(f"/api/{route}/stream", json=payload)
                self.assertIn("text/event-stream", response.headers["content-type"])
                events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")]
                self.assertEqual(events, [{"type": "delta", "text": "Hello\n"}, {"type": "delta", "text": "مرحبا"}, {"type": "done"}])

    def test_interrupted_stream_keeps_partial_output_and_reports_error(self):
        def failed(*args):
            yield "Partial copy"
            raise RuntimeError("secret upstream details")
        with patch("copywriter.stream_enhance_feedback", side_effect=failed):
            response = TestClient(app, headers={"X-User-Email": "b2b.admin@eand.ae"}).post("/api/enhance/stream", json={"feedback": "Brief"})
        self.assertIn("Partial copy", response.text)
        self.assertIn('"type": "error"', response.text)
        self.assertNotIn('"type": "done"', response.text)
        self.assertNotIn("secret", response.text)

    def test_sdk_deltas_arrive_before_completion_and_resources_close(self):
        with patch("ai_service.get_client") as get_client, patch("ai_service.get_model", return_value="model"):
            create = get_client.return_value.__enter__.return_value.chat.completions.create
            stream = create.return_value.__enter__.return_value
            stream.__iter__.return_value = iter([
                SimpleNamespace(choices=[]),
                chunk("Hello"),
                chunk(finish_reason="stop"),
            ])
            chunks = ai_service.stream_response_text("Instructions", "Input")
            self.assertEqual(next(chunks), "Hello")
            create.return_value.__exit__.assert_not_called()
            self.assertEqual(list(chunks), [])
            self.assertTrue(create.call_args.kwargs["stream"])
            create.return_value.__exit__.assert_called_once()

    def test_sdk_rejects_incomplete_empty_and_disconnected_streams(self):
        for events in [[], [chunk(finish_reason="stop")], [chunk(finish_reason="length")], [chunk(finish_reason="content_filter")]]:
            with patch("ai_service.get_client") as get_client, patch("ai_service.get_model", return_value="model"):
                stream = get_client.return_value.__enter__.return_value.chat.completions.create.return_value.__enter__.return_value
                stream.__iter__.return_value = iter(events)
                with self.assertRaises(ValueError):
                    list(ai_service.stream_response_text("Instructions", "Input"))

    def test_english_generation_retains_guidelines(self):
        with patch("ai_service.guidelines_for_text", return_value="Brand rules"), patch("ai_service.stream_response_text", return_value=iter(["Hello"])) as stream:
            self.assertEqual(list(ai_service.stream_enhance_feedback("مرحبا", "improve", "SMS", "Youth")), ["Hello"])
            self.assertIn("Brand rules", stream.call_args.args[0])
            self.assertIn("English only", stream.call_args.args[0])

    def test_arabic_generation_uses_quality_rules_and_user_details(self):
        with patch("ai_service.guidelines_for_text", return_value="Brand rules"), patch("ai_service._run_completion", return_value="نص واضح") as completion:
            self.assertEqual(list(ai_service.stream_enhance_feedback("Brief", "write", "Website", "Business", "b2b", "Use one CTA", "ar")), ["نص واضح"])
            instructions = completion.call_args.args[0]
            self.assertIn("Modern Standard Arabic", instructions)
            self.assertIn("Use one CTA", instructions)

    def test_invalid_input_is_rejected_before_stream(self):
        client = TestClient(app, headers={"X-User-Email": "b2b.admin@eand.ae"})
        self.assertEqual(client.post("/api/enhance/stream", json={"feedback": " "}).status_code, 422)
        self.assertEqual(client.post("/api/translate/stream", json={"generated": "Hello", "language": "fr"}).status_code, 422)
