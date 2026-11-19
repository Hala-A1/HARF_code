"""One private runtime environment, independent of the launch directory."""
from io import StringIO
from pathlib import Path
from threading import RLock
from functools import wraps
from dotenv import load_dotenv
from dotenv.parser import parse_stream

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'
CONFIG_LOCK = RLock()


def configuration_change(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with CONFIG_LOCK:
            return function(*args, **kwargs)
    return wrapped


def load_environment():
    # Deployment-injected environment variables take precedence.
    load_dotenv(ENV_FILE, override=False)


def updated_content(path, values):
    """Change only named keys; preserve credentials, unrelated settings and comments."""
    path = Path(path)
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    seen, result = set(), []
    def line(key):
        value = str(values[key]).replace('\\', '\\\\').replace("'", "\\'")
        return f"{key}='{value}'\n"
    for binding in parse_stream(StringIO(original)):
        if binding.key in values:
            if binding.key not in seen:
                result.append(line(binding.key))
                seen.add(binding.key)
        else:
            result.append(binding.original.string)
    text = ''.join(result)
    if text and not text.endswith('\n'):
        text += '\n'
    return text + ''.join(line(key) for key in values if key not in seen)


load_environment()
