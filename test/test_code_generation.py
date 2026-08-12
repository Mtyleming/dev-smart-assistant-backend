"""代码生成：安全过滤、子模式判定、格式化单测（不依赖真 LLM）。

用法（项目根目录）：

    python test/test_code_generation.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.services.code_generation_service import (
    format_generation_answer,
    normalize_generate_result,
    normalize_intent_result,
    resolve_mode,
)
from app.services.code_safety_filter import filter_code


class ResolveModeTest(unittest.TestCase):
    def test_no_code_is_generate(self) -> None:
        self.assertEqual(resolve_mode("用 Python 写一个快速排序", has_code=False), "generate")

    def test_code_with_analyze_is_analyze(self) -> None:
        self.assertEqual(
            resolve_mode("请解读这段代码的逻辑", has_code=True),
            "analyze",
        )

    def test_code_with_edit_is_edit(self) -> None:
        self.assertEqual(
            resolve_mode("请帮我改一下，加上错误处理", has_code=True),
            "edit",
        )

    def test_code_with_generate_keyword_is_edit(self) -> None:
        self.assertEqual(
            resolve_mode("基于这段帮我写一个更完整的版本", has_code=True),
            "edit",
        )

    def test_code_without_keyword_defaults_analyze(self) -> None:
        self.assertEqual(resolve_mode("```python\nprint(1)\n```", has_code=True), "analyze")


class SafetyFilterTest(unittest.TestCase):
    def test_hardcoded_api_key_replaced(self) -> None:
        code = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"\nprint(api_key)\n'
        filtered, flags = filter_code(code)
        self.assertTrue(any(f.get("kind") == "secret" for f in flags))
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", filtered)
        self.assertIn("os.environ.get", filtered)

    def test_os_system_commented(self) -> None:
        code = 'import os\nos.system("rm -rf /")\n'
        filtered, flags = filter_code(code)
        self.assertTrue(any(f.get("kind") == "dangerous_call" for f in flags))
        self.assertIn("[安全过滤:os.system]", filtered)
        self.assertNotRegex(filtered, r"(?m)^\s*os\.system\(")

    def test_eval_commented(self) -> None:
        code = 'x = eval(user_input)\n'
        filtered, flags = filter_code(code)
        self.assertTrue(flags)
        self.assertIn("[安全过滤:eval]", filtered)

    def test_clean_code_unchanged(self) -> None:
        code = "def add(a, b):\n    return a + b\n"
        filtered, flags = filter_code(code)
        self.assertEqual(filtered, code)
        self.assertEqual(flags, [])


class NormalizeAndFormatTest(unittest.TestCase):
    def test_normalize_intent_forces_generate_without_reference(self) -> None:
        result = normalize_intent_result(
            {"mode": "edit", "language": "python", "requirements": "排序"},
            hint_mode="generate",
            has_reference=False,
        )
        self.assertEqual(result["mode"], "generate")
        self.assertEqual(result["language"], "python")

    def test_normalize_intent_forces_edit_with_reference(self) -> None:
        result = normalize_intent_result(
            {"mode": "generate", "language": "go"},
            hint_mode="edit",
            has_reference=True,
        )
        self.assertEqual(result["mode"], "edit")

    def test_normalize_generate_result(self) -> None:
        result = normalize_generate_result(
            {
                "code": "print(1)",
                "language": "python",
                "usage": "直接运行",
                "dependencies": ["无"],
            },
            fallback_language="text",
        )
        self.assertEqual(result["code"], "print(1)")
        self.assertEqual(result["dependencies"], ["无"])

    def test_format_generation_answer_generate(self) -> None:
        md = format_generation_answer(
            {
                "mode": "generate",
                "language": "python",
                "code": "print('hi')",
                "usage": "运行脚本",
                "dependencies": ["Python 3.12"],
                "safety_flags": [],
                "spec_injected": True,
                "disclaimer": "由 AI 生成，建议 Code Review 后使用",
            }
        )
        self.assertIn("## 生成代码（python）", md)
        self.assertIn("```python", md)
        self.assertIn("print('hi')", md)
        self.assertIn("### 使用说明", md)
        self.assertIn("### 依赖说明", md)
        self.assertIn("已对照团队知识库中的编码规范生成", md)
        self.assertIn("由 AI 生成", md)

    def test_format_generation_answer_edit_with_flags(self) -> None:
        md = format_generation_answer(
            {
                "mode": "edit",
                "language": "python",
                "code": "# safe",
                "usage": "替换原文件",
                "dependencies": [],
                "safety_flags": [
                    {"kind": "secret", "detail": "已替换密钥"},
                ],
                "spec_injected": False,
            }
        )
        self.assertIn("## 改写代码（python）", md)
        self.assertIn("### 安全过滤", md)
        self.assertIn("已替换密钥", md)
        self.assertIn("- 无额外依赖", md)


if __name__ == "__main__":
    unittest.main()
