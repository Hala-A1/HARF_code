# Local token counting

The bundled `cl100k_base` and `o200k_base` vocabularies and encoding metadata come from OpenAI tiktoken. They are loaded from local files; input text never leaves the application for token counting, and runtime token checks make no tokenizer downloads.

Source: https://github.com/openai/tiktoken (MIT license; see LICENSE).

Supported model names use the corresponding tokenizer with a framing allowance. Unrecognised deployment/model names use a conservative UTF-8 byte estimate. Images receive an estimated vision allowance rather than counting their base64 encoding as text. Provider-reported actual usage remains separate from these preflight estimates.
