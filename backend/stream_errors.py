from openai import APIConnectionError, APITimeoutError, APIStatusError


class StreamFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stream_error_details(error):
    code = getattr(error, "code", None)
    status = getattr(error, "status_code", None)
    if isinstance(error, APITimeoutError):
        code = "timeout"
    elif isinstance(error, APIConnectionError):
        code = "connection_error"
    elif isinstance(error, APIStatusError):
        code = {401: "configuration", 403: "configuration", 404: "configuration", 408: "timeout", 429: "rate_limit_exceeded"}.get(status, code)
        if isinstance(getattr(error, 'body', None), dict) and error.body.get('code') == 'llm_rate_limit':
            code = 'llm_rate_limit'
        if status >= 500:
            code = "server_error"
    messages = {
        "input_token_limit": (str(error), False),
        "inference_policy": (str(error), False),
        "llm_rate_limit": ("AI request capacity is busy. Please wait a moment and retry.", True),
        "timeout": ("The AI service took too long to respond. Please retry.", True),
        "connection_error": ("The backend could not connect to the AI service. Please retry.", True),
        "stream_disconnected": ("The AI connection closed before the text was complete. Please retry.", True),
        "rate_limit_exceeded": ("The AI service is receiving too many requests. Please wait a moment and retry.", True),
        "server_error": ("The AI service is temporarily unavailable. Please retry.", True),
        "content_filter": ("The AI service filtered this request. Please revise the text.", False),
        "max_output_tokens": ("The AI response reached its output limit. Please try a shorter text.", False),
        "configuration": ("The backend cannot access the configured AI model. Check its credentials and deployment.", False),
        "empty_output": ("The AI service returned no text. Please revise the text and retry.", False),
        "component_validation_failed": ("A generated component did not meet its required field limits or writing rules. Review the specific component details and retry.", False),
        "component_response_invalid": ("The AI returned an incomplete component response after automatic recovery. Please retry this component.", True),
    }
    message, retryable = messages.get(code, ("The AI request failed. Please retry; the backend log has diagnostic details.", False))
    return {"type": "error", "code": code if code in messages else "generation_failed", "message": message, "retryable": retryable}
