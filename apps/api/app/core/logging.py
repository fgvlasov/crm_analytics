import logging
import re
import sys


_PATTERNS = [
    (re.compile(r"(?i)(password\s*[=:]\s*)(\S+)"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)(\S+)"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(authorization\s*[=:]\s*)(bearer\s+)?(\S+)"), r"\1\2***REDACTED***"),
    (re.compile(r"(?i)(secret\s*[=:]\s*)(\S+)"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(token\s*[=:]\s*)(\S+)"), r"\1***REDACTED***"),
]


def redact_secrets(value: str) -> str:
    out = value
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secrets(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(a) if isinstance(a, str) else a for a in record.args
                )
        return True


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
