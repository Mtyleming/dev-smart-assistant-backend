"""代码安全过滤：检测硬编码密钥与危险系统调用，并做脱敏/告警。"""

from __future__ import annotations

import re
from typing import Any

# 危险调用：命中后将该行改为注释告警（不执行等价逻辑）
_DANGEROUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "os.system",
        re.compile(r"(?P<prefix>^\s*)(?P<body>.*\bos\.system\s*\()", re.M),
    ),
    (
        "subprocess_shell",
        re.compile(
            r"(?P<prefix>^\s*)(?P<body>.*\bsubprocess\.(?:call|run|Popen)\s*\([^)\n]*shell\s*=\s*True)",
            re.M,
        ),
    ),
    (
        "eval",
        re.compile(r"(?P<prefix>^\s*)(?P<body>.*(?<![.\w])eval\s*\()", re.M),
    ),
    (
        "exec",
        re.compile(r"(?P<prefix>^\s*)(?P<body>.*(?<![.\w])exec\s*\()", re.M),
    ),
    (
        "pickle.loads",
        re.compile(r"(?P<prefix>^\s*)(?P<body>.*\bpickle\.loads\s*\()", re.M),
    ),
    (
        "runtime_exec",
        re.compile(
            r"(?P<prefix>^\s*)(?P<body>.*Runtime\.getRuntime\(\)\.exec\s*\()",
            re.M,
        ),
    ),
]

# 硬编码密钥 / Token：替换为环境变量占位
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "aws_access_key",
        re.compile(
            r'(?P<prefix>)(?P<quote>["\'])(?P<value>AKIA[0-9A-Z]{16})(?P=quote)'
        ),
        'os.environ.get("AWS_ACCESS_KEY_ID", "")',
    ),
    (
        "openai_sk",
        re.compile(
            r'(?P<prefix>)(?P<quote>["\'])(?P<value>sk-[A-Za-z0-9]{20,})(?P=quote)'
        ),
        'os.environ.get("API_KEY", "")',
    ),
    (
        "assignment_secret",
        re.compile(
            r"(?P<prefix>\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|"
            r"auth[_-]?token|password|passwd|secret|token)\b\s*"
            r"(?:=|:)\s*)"
            r"(?P<quote>['\"])"
            r"(?P<value>(?!\s*\{)[^'\"\n]{8,})"
            r"(?P=quote)",
            re.IGNORECASE,
        ),
        'os.environ.get("API_KEY", "")',
    ),
]


def _comment_line(prefix: str, body: str, flag: str) -> str:
    """将危险行改成注释告警。"""
    stripped = body.rstrip("\n")
    return f"{prefix}# [安全过滤:{flag}] 已禁用危险调用 → {stripped}"


def filter_code(code: str) -> tuple[str, list[dict[str, Any]]]:
    """对生成代码做安全过滤。

    Returns:
        (filtered_code, safety_flags)
        safety_flags 每项含 kind / pattern / detail
    """
    text = code or ""
    flags: list[dict[str, Any]] = []

    # 1) 密钥脱敏
    for kind, pattern, replacement in _SECRET_PATTERNS:
        def _secret_repl(match: re.Match[str], *, _kind: str = kind, _rep: str = replacement) -> str:
            flags.append(
                {
                    "kind": "secret",
                    "pattern": _kind,
                    "detail": "检测到疑似硬编码密钥，已替换为环境变量占位",
                }
            )
            prefix = match.groupdict().get("prefix") or ""
            return f"{prefix}{_rep}"

        text, count = pattern.subn(_secret_repl, text)
        # count 已在回调里记 flag；避免重复无需再处理

    # 2) 危险调用：按行注释
    lines = text.splitlines(keepends=True)
    if not lines and text:
        lines = [text]

    new_lines: list[str] = []
    for line in lines:
        replaced = False
        for kind, pattern in _DANGEROUS_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            # 已是注释则跳过
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                break
            prefix = match.group("prefix") or ""
            # 保留原行缩进，整行注释
            indent = line[: len(line) - len(line.lstrip())]
            body = line[len(indent) :]
            new_lines.append(_comment_line(indent, body, kind) + ("\n" if line.endswith("\n") else ""))
            flags.append(
                {
                    "kind": "dangerous_call",
                    "pattern": kind,
                    "detail": f"检测到危险调用 {kind}，已注释禁用",
                }
            )
            replaced = True
            break
        if not replaced:
            new_lines.append(line)

    return "".join(new_lines), flags
