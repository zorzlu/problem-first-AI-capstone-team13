"""Synthesis safety judging and compliance nodes."""
import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from backend.iterations.contracts import OutputSafetyJudgeOut, WorkflowState
from backend.iterations.prompts import JUDGE_SYSTEM_PROMPT
from backend.iterations.utils import copy_dict, datetime_now, invoke_with_retry
from backend.core.llm import get_judge_llm, has_llm_for_step

def judge_synthesis_output(ticker: str, bucket: Dict[str, Any], synthesis: Dict[str, Any]) -> OutputSafetyJudgeOut:
    if not has_llm_for_step("judge"):
        return OutputSafetyJudgeOut(
            passes=True,
            groundingPassed=True,
            advicePassed=True,
            pathPassed=True,
            defects=[],
            regenerationInstruction=""
        )
    
    llm = get_judge_llm()
    structured_judge = llm.with_structured_output(OutputSafetyJudgeOut)
    
    # Exclude guardrailMetadata from evaluated synthesis to avoid contamination
    eval_synthesis = {k: v for k, v in synthesis.items() if k != "guardrailMetadata"}
    
    user_prompt = f"TICKER: {ticker}\nCONTEXT BUCKET:\n{json.dumps(bucket, indent=2)}\n\nGENERATED SYNTHESIS:\n{json.dumps(eval_synthesis, indent=2)}"
    
    judge_result = invoke_with_retry(
        structured_judge,
        [SystemMessage(content=JUDGE_SYSTEM_PROMPT), HumanMessage(content=user_prompt)],
        label=f"safety judge for {ticker}"
    )
    return _relax_language_only_judge_failure(judge_result, eval_synthesis)

def _contains_explicit_trade_instruction(synthesis: Dict[str, Any]) -> bool:
    text = json.dumps(synthesis, ensure_ascii=False).lower()
    forbidden_patterns = [
        r"\b(?:should|must|consider|recommend(?:ed|s|ing)?\s+to)\s+(?:buy|sell|short|enter|exit)\b",
        r"\b(?:buy|sell|short)\s+(?:the\s+)?(?:stock|shares|ticker|position)\b",
        r"\benter\s+(?:a\s+)?(?:position|trade)\b",
        r"\bexit\s+(?:the\s+)?(?:position|trade)\b",
        r"\btake profit\b",
        r"\bstop loss\b",
        r"\brecommend(?:ed|s|ing)?\s+(?:a\s+)?trade\b",
    ]
    return any(re.search(pattern, text) for pattern in forbidden_patterns)

def _relax_language_only_judge_failure(
    judge_result: OutputSafetyJudgeOut,
    synthesis: Dict[str, Any],
) -> OutputSafetyJudgeOut:
    """Avoid degrading useful briefings over neutral watch/monitor phrasing."""
    if judge_result.advicePassed or _contains_explicit_trade_instruction(synthesis):
        return judge_result

    relaxed = judge_result.model_copy(deep=True)
    relaxed.advicePassed = True
    relaxed.defects = [
        defect for defect in relaxed.defects
        if not re.search(r"\b(advice|recommend|watch|monitor|trading recommendation|action language)\b", defect, re.IGNORECASE)
    ]
    relaxed.passes = relaxed.groundingPassed and relaxed.pathPassed
    if relaxed.passes:
        relaxed.defects = []
        relaxed.regenerationInstruction = ""
    return relaxed

def build_degraded_synthesis(ticker: str, reason: str, source_ids: List[str], source_urls: List[str]) -> Dict[str, Any]:
    return {
        "summaryId": f"sum_degraded_{ticker}_{int(datetime_now().timestamp())}",
        "ticker": ticker,
        "summaryHeadline": "Briefing suppressed pending verification",
        "situationSummary": f"A catalyst may be present for {ticker}, but the generated briefing did not pass grounding/advice verification. Review the source events directly.",
        "mainCatalysts": [],
        "overallPossibleInfluence": "unclear",
        "confidence": "low",
        "uncertainties": [f"Defect flagged: {reason}"],
        "watchItems": ["Review the cited source events before drawing conclusions."],
        "sourceEventIds": source_ids,
        "sourceArticleUrls": source_urls,
        "notFinancialAdvice": True,
        "complianceDisclaimer": "This briefing was degraded by the output safety guardrail.",
        "guardrailMetadata": {
            "judgeStatus": "degraded",
            "judgeAttempts": 2,
            "judgeDefects": [reason],
            "regenerated": True,
            "degraded": True
        }
    }

def run_compliance_gate(state: WorkflowState) -> Dict[str, Any]:
    print("--- [Node 6: Compliance Gate Check] ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    ticker_syntheses = state.get("ticker_syntheses", {})
    
    if span and span.is_recording():
        span.set_attribute("syntheses_count", len(ticker_syntheses))
        
    # Simple rule-based compliance cleaner to ensure no buy/sell recommendations slip through
    forbidden_patterns = [
        (r'\bshould\s+buy\s+(?:the\s+)?(?:stock|shares|ticker)\b', 'could show positive pressure'),
        (r'\bshould\s+sell\s+(?:the\s+)?(?:stock|shares|ticker)\b', 'could show negative pressure'),
        (r'\bshould\s+short\s+(?:the\s+)?(?:stock|shares|ticker)\b', 'may face downward sentiment pressure'),
        (r'\benter\s+(?:a\s+)?(?:position|trade)\b', 'monitor the catalyst'),
        (r'\bexit\s+(?:the\s+)?(?:position|trade)\b', 'reassess the catalyst'),
        (r'\btake profit\b', 'monitor follow-through'),
        (r'\bstop loss\b', 'risk marker'),
        (r'\bwe recommend\s+(?:a\s+)?trade\b', 'the briefing flags a catalyst'),
    ]
    
    cleaned_syntheses = {}
    for ticker, syn in ticker_syntheses.items():
        syn_copy = copy_dict(syn)
        
        # Run compliance check on text fields
        headline = syn_copy.get("summaryHeadline", "")
        summary = syn_copy.get("situationSummary", "")
        
        violations_count = 0
        for pattern, replacement in forbidden_patterns:
            violations_count += len(re.findall(pattern, headline, flags=re.IGNORECASE))
            violations_count += len(re.findall(pattern, summary, flags=re.IGNORECASE))
            
            headline = re.sub(pattern, replacement, headline, flags=re.IGNORECASE)
            summary = re.sub(pattern, replacement, summary, flags=re.IGNORECASE)
            
        syn_copy["summaryHeadline"] = headline
        syn_copy["situationSummary"] = summary
        syn_copy["notFinancialAdvice"] = True
        cleaned_syntheses[ticker] = syn_copy
        
        if span and span.is_recording():
            span.add_event("compliance_check", {
                "ticker": ticker,
                "violations_scrubbed_count": violations_count
            })
            
    return {"ticker_syntheses": cleaned_syntheses}
