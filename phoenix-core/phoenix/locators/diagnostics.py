"""Useful local locator diagnostics with supplied data and secrets removed."""
import os


def redact_diagnostics(value, manual_tests=()):
    secrets = [v for k, v in os.environ.items() if v and any(
        word in k.upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'USERNAME', 'EMAIL'))]
    for case in manual_tests:
        for step in case.get('steps', []):
            data = str(step.get('test_data') or '').strip().strip('`\"\'')
            if data:
                secrets.append(data)
    secrets = sorted(set(secrets), key=len, reverse=True)
    def redact(item):
        if isinstance(item, str):
            for secret in secrets:
                item = item.replace(secret, '[REDACTED]')
            return item
        if isinstance(item, dict):
            return {k: redact(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [redact(v) for v in item]
        return item
    return redact(value)
