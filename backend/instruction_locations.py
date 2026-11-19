"""Current instruction layout and compatibility with older recovery artifacts."""
from pathlib import Path, PurePosixPath

INSTRUCTIONS_ROOT = Path(__file__).resolve().parents[1] / 'instructions'
LEGACY_PREFIX = 'Copywriter/backend/prompt/'


def instruction_relative_path(relative):
    """Validate and map an old/new snapshot path into the current folder."""
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('Invalid instruction file path.')
    prefix = next((p for p in ('instructions/', LEGACY_PREFIX) if relative.startswith(p)), None)
    if prefix is None:
        raise ValueError('Unexpected instruction file path in source snapshot.')
    tail = relative[len(prefix):]
    if not tail or any(p in {'', '.', '..'} for p in tail.split('/')) or ':' in tail:
        raise ValueError('Invalid instruction file path.')
    return str(PurePosixPath('instructions') / tail)


def instruction_restore_path(root, relative):
    path = root / instruction_relative_path(relative)
    if not path.resolve().is_relative_to((root / 'instructions').resolve()):
        raise ValueError('Invalid instruction restore path.')
    return path
