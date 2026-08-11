"""代码解析工具：抽代码、检测语言、轻量结构化、解析 LLM JSON。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound

logger = logging.getLogger(__name__)

# Pygments lexer 名称 / 别名 → 本项目规范语言名
_PYGMENTS_NAME_MAP: dict[str, str] = {
    "python": "python",
    "python 3": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "go": "go",
    "sql": "sql",
    "c++": "cpp",
    "cpp": "cpp",
    "c": "c",
    "c#": "csharp",
    "csharp": "csharp",
    "rust": "rust",
    "ruby": "ruby",
    "bash": "shell",
    "shell": "shell",
    "shell session": "shell",
    "kotlin": "kotlin",
    "swift": "swift",
    "php": "php",
}

# Markdown 围栏：```lang\n...\n```
_FENCE_RE = re.compile(
    r"```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```",
    re.MULTILINE,
)

_LANG_ALIASES: dict[str, str] = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "golang": "go",
    "c++": "cpp",
    "c#": "csharp",
    "cs": "csharp",
    "rs": "rust",
    "rb": "ruby",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
}

_SUPPORTED_LANGUAGES = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "java",
        "go",
        "sql",
        "cpp",
        "c",
        "csharp",
        "rust",
        "ruby",
        "shell",
        "kotlin",
        "swift",
        "php",
    }
)

_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)```",
    re.IGNORECASE,
)


class CodeParser:
    """从用户消息中提取代码并做轻量结构分析。"""

    def extract_code(
        self,
        message: str,
        *,
        content_type: str | None = None,
    ) -> tuple[str, str | None]:
        """从消息中提取代码正文与可选围栏语言。

        Returns:
            (code, fence_lang)。无有效代码时 code 为空字符串。
        """
        text = (message or "").strip()
        if not text:
            return "", None

        fences = list(_FENCE_RE.finditer(text))
        if fences:
            # 取最长的代码块（通常是用户粘贴的主体）
            best = max(fences, key=lambda m: len(m.group(2) or ""))
            fence_lang = (best.group(1) or "").strip().lower() or None
            code = (best.group(2) or "").strip()
            if code:
                return code, fence_lang

        # content_type=code：整段视为代码
        if content_type == "code":
            return text, None

        # 无围栏但看起来像代码：至少 2 行且含常见代码符号
        lines = text.splitlines()
        if len(lines) >= 2 and self._looks_like_code(text):
            return text, None

        return "", None

    def detect_language(
        self,
        code: str,
        fence_lang: str | None = None,
    ) -> str | None:
        """检测编程语言；优先级：Markdown 围栏 → Pygments → 正则特征。"""
        # 1) Markdown 代码块标记（```python）
        if fence_lang:
            normalized = self._normalize_lang_token(fence_lang)
            if normalized:
                return normalized

        sample = code or ""
        if not sample.strip():
            return None

        # 2) Pygments 启发式探测
        guessed = self._detect_language_by_pygments(sample)
        if guessed:
            return guessed

        # 3) 正则特征回退
        return self._detect_language_by_regex(sample)

    @staticmethod
    def _normalize_lang_token(token: str) -> str | None:
        """将围栏 / 别名规范化为本项目支持的语言名。"""
        key = (token or "").strip().lower()
        if not key:
            return None
        normalized = _LANG_ALIASES.get(key, key)
        if normalized in _SUPPORTED_LANGUAGES:
            return normalized
        return None

    def _detect_language_by_pygments(self, code: str) -> str | None:
        """用 pygments.lexers.guess_lexer 探测语言。"""
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            return None
        except Exception as exc:
            logger.debug("Pygments 语言探测失败: %s", exc)
            return None

        candidates: list[str] = []
        name = str(getattr(lexer, "name", "") or "").strip()
        if name:
            candidates.append(name.lower())
        aliases = getattr(lexer, "aliases", None) or []
        for alias in aliases:
            if alias:
                candidates.append(str(alias).strip().lower())

        for token in candidates:
            mapped = _PYGMENTS_NAME_MAP.get(token)
            if mapped and mapped in _SUPPORTED_LANGUAGES:
                return mapped
            normalized = self._normalize_lang_token(token)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _detect_language_by_regex(sample: str) -> str | None:
        """基于常见语法特征的正则回退识别。"""
        # Python
        if re.search(r"^\s*(def |class |import |from \w+ import |async def )", sample, re.M):
            return "python"
        # TypeScript（优先于 JS）
        if re.search(r"\b(interface |type \w+\s*=|:\s*\w+(\[\])?\s*[=;])", sample) and re.search(
            r"\b(function |const |let |export |import )", sample
        ):
            return "typescript"
        # JavaScript
        if re.search(
            r"^\s*(function |const |let |var |export |import |=>)",
            sample,
            re.M,
        ) or re.search(r"\bconsole\.log\b", sample):
            return "javascript"
        # Java
        if re.search(r"\b(public |private |protected )?(class |interface )", sample) and (
            "System.out" in sample or re.search(r"\bvoid\s+\w+\s*\(", sample)
        ):
            return "java"
        # Go
        if re.search(r"^\s*package\s+\w+", sample, re.M) or re.search(
            r"^\s*func\s+", sample, re.M
        ):
            return "go"
        # SQL
        if re.search(
            r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|ALTER TABLE)\b",
            sample,
            re.I,
        ):
            return "sql"
        # C / C++
        if re.search(r"#include\s*[<\"]", sample):
            if re.search(r"\bstd::|cout\s*<<|cin\s*>>", sample):
                return "cpp"
            return "c"
        # C#
        if re.search(r"\bnamespace\s+\w+|using\s+System\b", sample):
            return "csharp"
        # Rust
        if re.search(r"^\s*(fn |mod |use |impl |pub fn )", sample, re.M):
            return "rust"
        # Ruby
        if re.search(r"^\s*(def |class |require |module )", sample, re.M) and "end" in sample:
            return "ruby"
        # Shell
        if re.search(r"^#!/(usr/)?bin/(ba)?sh", sample) or re.search(
            r"^\s*(echo |export |if \[|fi$)", sample, re.M
        ):
            return "shell"
        # Kotlin
        if re.search(r"\b(fun |val |var |companion object)", sample):
            return "kotlin"
        # Swift
        if re.search(r"\b(func |let |var |import Foundation)", sample):
            return "swift"
        # PHP
        if "<?php" in sample or re.search(r"\$\w+\s*=", sample):
            return "php"

        return None

    def parse_structure(self, code: str, language: str | None = None) -> dict[str, Any]:
        """轻量正则抽取函数/类名列表。"""
        functions: list[str] = []
        classes: list[str] = []
        text = code or ""
        lang = (language or "").lower()

        if lang == "python":
            functions.extend(re.findall(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", text, re.M))
            classes.extend(re.findall(r"^\s*class\s+(\w+)\s*[:(]", text, re.M))
        elif lang in {"javascript", "typescript"}:
            functions.extend(re.findall(r"^\s*(?:export\s+)?function\s+(\w+)\s*\(", text, re.M))
            functions.extend(
                re.findall(
                    r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(",
                    text,
                    re.M,
                )
            )
            classes.extend(re.findall(r"^\s*(?:export\s+)?class\s+(\w+)\b", text, re.M))
        elif lang == "java":
            classes.extend(
                re.findall(
                    r"\b(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?class\s+(\w+)",
                    text,
                )
            )
            functions.extend(
                re.findall(
                    r"\b(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(",
                    text,
                )
            )
        elif lang == "go":
            functions.extend(re.findall(r"^\s*func\s+(?:\([\w\s*]+\)\s+)?(\w+)\s*\(", text, re.M))
            classes.extend(re.findall(r"^\s*type\s+(\w+)\s+struct\b", text, re.M))
        elif lang == "sql":
            functions.extend(
                re.findall(
                    r"\b(?:CREATE|ALTER|DROP)\s+(?:TABLE|VIEW|INDEX|PROCEDURE)\s+(\w+)",
                    text,
                    re.I,
                )
            )
        else:
            # 通用兜底
            functions.extend(re.findall(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", text, re.M))
            functions.extend(re.findall(r"^\s*function\s+(\w+)\s*\(", text, re.M))
            functions.extend(re.findall(r"^\s*func\s+(\w+)\s*\(", text, re.M))
            classes.extend(re.findall(r"^\s*class\s+(\w+)\b", text, re.M))

        # 去重保序
        def _unique(items: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for name in items:
                if name not in seen:
                    seen.add(name)
                    out.append(name)
            return out

        return {
            "language": lang or None,
            "functions": _unique(functions),
            "classes": _unique(classes),
            "line_count": len(text.splitlines()) if text else 0,
        }

    def parse_llm_response(self, text: str) -> dict[str, Any]:
        """从模型输出中提取 JSON；失败时降级为 summary 兜底结构。"""
        content = (text or "").strip()
        if not content:
            return self._fallback_result("模型未返回有效内容")

        parsed = self._try_parse_json(content)
        if parsed is not None:
            return self._normalize_result(parsed, raw=content)

        fence = _JSON_FENCE_RE.search(content)
        if fence:
            parsed = self._try_parse_json(fence.group(1).strip())
            if parsed is not None:
                return self._normalize_result(parsed, raw=content)

        # 尝试抠第一个 { ... } 块（含嵌套的简单平衡扫描）
        brace_block = self._extract_balanced_json(content)
        if brace_block:
            parsed = self._try_parse_json(brace_block)
            if parsed is not None:
                return self._normalize_result(parsed, raw=content)

        logger.warning("代码分析 LLM 输出无法解析为 JSON，使用原文兜底")
        summary = content[:50].replace("\n", " ")
        return self._fallback_result(summary or "分析完成", raw=content)

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """粗判文本是否像源代码。"""
        markers = (
            "{",
            "}",
            ";",
            "=>",
            "def ",
            "function ",
            "class ",
            "import ",
            "return ",
            "const ",
            "public ",
            "func ",
            "SELECT ",
        )
        hit = sum(1 for m in markers if m in text)
        return hit >= 2

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any] | None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _extract_balanced_json(text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    @staticmethod
    def _fallback_result(summary: str, *, raw: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "summary": summary[:50],
            "logic_explanation": raw or summary,
            "data_flow": "",
            "issues": [],
            "optimization": [],
        }
        return result

    @staticmethod
    def _normalize_result(data: dict[str, Any], *, raw: str) -> dict[str, Any]:
        issues = data.get("issues")
        if not isinstance(issues, list):
            issues = []
        optimization = data.get("optimization")
        if not isinstance(optimization, list):
            optimization = []
        return {
            "summary": str(data.get("summary") or "")[:80] or "代码分析结果",
            "logic_explanation": str(
                data.get("logic_explanation") or data.get("logic") or raw
            ),
            "data_flow": str(data.get("data_flow") or ""),
            "issues": issues,
            "optimization": optimization,
        }
