"""
评估引擎 - 自动评估、A/B 测试（模拟模式）
"""
from __future__ import annotations

import random
import statistics
from datetime import datetime
from typing import Any

from models import (
    ABTest,
    ABTestStatus,
    ABTestVariant,
    EvalMetric,
    EvalResult,
    Prompt,
)
from template_engine import TemplateEngine


# ── 模拟 LLM 调用 ────────────────────────────────────────────────────────
_MOCK_RESPONSES = {
    "summarize": "这是一个简洁准确的摘要，涵盖了原文的核心要点。",
    "translate": "The translation is fluent and accurately conveys the original meaning.",
    "code": "```python\ndef solve():\n    return 42\n```\n\n以上代码实现了所需功能。",
    "default": "根据您的要求，以下是详细的回答内容。",
}


def _mock_llm_call(rendered_prompt: str, model_hint: str = "") -> str:
    """模拟 LLM 返回 (不实际调用 API)"""
    lower = rendered_prompt.lower()
    for keyword, resp in _MOCK_RESPONSES.items():
        if keyword in lower:
            return resp
    return _MOCK_RESPONSES["default"]


# ── 评分模拟器 ────────────────────────────────────────────────────────────
class _MockScorer:
    """模拟评分器 - 根据启发式规则给出评分"""

    @staticmethod
    def score_accuracy(prompt: str, output: str) -> float:
        base = 0.6
        if len(output) > 20:
            base += 0.1
        if len(prompt) > 50:
            base += 0.05
        return min(1.0, base + random.uniform(-0.05, 0.15))

    @staticmethod
    def score_relevance(prompt: str, output: str) -> float:
        prompt_words = set(prompt.lower().split())
        output_words = set(output.lower().split())
        overlap = len(prompt_words & output_words)
        base = min(0.9, 0.5 + overlap * 0.03)
        return min(1.0, base + random.uniform(-0.05, 0.1))

    @staticmethod
    def score_format(prompt: str, output: str) -> float:
        base = 0.7
        if "```" in output:
            base += 0.1
        if "\n" in output:
            base += 0.05
        return min(1.0, base + random.uniform(-0.05, 0.1))

    @staticmethod
    def score_fluency(prompt: str, output: str) -> float:
        sentences = [s.strip() for s in output.split("。") if s.strip()]
        base = min(0.9, 0.6 + len(sentences) * 0.05)
        return min(1.0, base + random.uniform(-0.03, 0.1))

    @staticmethod
    def score_completeness(prompt: str, output: str) -> float:
        base = 0.65
        if len(output) > 50:
            base += 0.15
        return min(1.0, base + random.uniform(-0.05, 0.15))


_METRIC_SCORERS = {
    EvalMetric.ACCURACY: _MockScorer.score_accuracy,
    EvalMetric.RELEVANCE: _MockScorer.score_relevance,
    EvalMetric.FORMAT: _MockScorer.score_format,
    EvalMetric.FLUENCY: _MockScorer.score_fluency,
    EvalMetric.COMPLETENESS: _MockScorer.score_completeness,
}


# ── 评估引擎 ──────────────────────────────────────────────────────────────
class Evaluator:
    """Prompt 评估引擎"""

    def __init__(self):
        self.engine = TemplateEngine()

    def evaluate_prompt(
        self,
        prompt: Prompt,
        metrics: list[EvalMetric] | None = None,
        samples: list[dict[str, Any]] | None = None,
    ) -> list[EvalResult]:
        """评估单个 Prompt"""
        metrics = metrics or list(EvalMetric)
        version = prompt.latest_version
        if not version:
            return []

        samples = samples or [{}]
        results: list[EvalResult] = []

        for sample in samples:
            try:
                rendered = self.engine.render(version.template, sample)
            except Exception:
                rendered = version.template

            output = _mock_llm_call(rendered, version.model_hint)

            for metric in metrics:
                scorer = _METRIC_SCORERS.get(metric)
                if not scorer:
                    continue
                score = scorer(rendered, output)
                results.append(
                    EvalResult(
                        prompt_id=prompt.id,
                        version=version.version,
                        metric=metric,
                        score=round(score, 4),
                        details=f"模拟评估 - {metric.value}",
                        input_sample=str(sample)[:200],
                        output_sample=output[:200],
                    )
                )

        return results

    def run_ab_test(
        self,
        test: ABTest,
        prompts: dict[str, Prompt],
    ) -> ABTest:
        """运行 A/B 测试"""
        if len(test.variants) < 2:
            raise ValueError("A/B 测试至少需要 2 个变体")

        test.status = ABTestStatus.RUNNING
        test.updated_at = datetime.utcnow()

        variant_scores: dict[int, list[float]] = {}

        for idx, variant in enumerate(test.variants):
            prompt = prompts.get(variant.prompt_id)
            if not prompt:
                continue

            scores: list[float] = []
            for _ in range(test.sample_size):
                sample = self._generate_random_sample()
                eval_results = self.evaluate_prompt(
                    prompt,
                    metrics=[EvalMetric.ACCURACY, EvalMetric.RELEVANCE],
                    samples=[sample],
                )
                avg = (
                    statistics.mean([r.score for r in eval_results])
                    if eval_results
                    else 0.0
                )
                scores.append(avg)

            variant_scores[idx] = scores

        # 汇总结果
        test.results = []
        best_idx, best_mean = 0, 0.0
        for idx, scores in variant_scores.items():
            mean_score = statistics.mean(scores) if scores else 0.0
            std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.0
            test.results.append({
                "variant_index": idx,
                "prompt_id": test.variants[idx].prompt_id,
                "version": test.variants[idx].version,
                "mean_score": round(mean_score, 4),
                "std_dev": round(std_dev, 4),
                "min_score": round(min(scores), 4) if scores else 0,
                "max_score": round(max(scores), 4) if scores else 0,
                "sample_size": len(scores),
            })
            if mean_score > best_mean:
                best_mean = mean_score
                best_idx = idx

        test.winner_variant_idx = best_idx
        test.status = ABTestStatus.COMPLETED
        test.updated_at = datetime.utcnow()

        return test

    @staticmethod
    def _generate_random_sample() -> dict[str, Any]:
        """生成随机测试样本"""
        topics = ["人工智能", "机器学习", "自然语言处理", "计算机视觉", "深度学习"]
        actions = ["总结", "翻译", "解释", "分析", "优化"]
        return {
            "topic": random.choice(topics),
            "action": random.choice(actions),
            "text": f"关于{random.choice(topics)}的技术文档",
            "language": "中文",
        }
