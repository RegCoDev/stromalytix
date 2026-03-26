"""
PI Chat: conversational interface grounded in company process context.

Different from BioSim chat (which elicits parameters). PI chat INTERPRETS
analyzed data, explains KPIs, investigates hypotheses, and synthesizes
simulation predictions with real process evidence.
"""
import os
import re
from typing import Optional

from dotenv import load_dotenv

from core.company_context import CompanyContext

load_dotenv()


def build_pi_system_prompt(context: CompanyContext) -> str:
    """
    Build system prompt grounded in company's process intelligence state.

    The prompt includes current context: flagged lots, open hypotheses,
    prediction accuracy, calibration data — so the LLM can reason over
    the company's actual state rather than hallucinating.
    """
    context_block = context.to_chat_context_string()

    # Build reading context from active signals
    reading_block = _build_reading_context(context)

    return f"""You are a Process Intelligence Analyst for Stromalytix.
You help biofabrication companies interpret their process data,
investigate root causes, and connect experimental parameters to
business outcomes.

CURRENT COMPANY CONTEXT:
{context_block}

RELEVANT READING (cite when applicable):
{reading_block}

YOUR CAPABILITIES:
- Interpret process mining KPIs and critical control points
- Investigate hypotheses about lot failures and process deviations
- Explain batch effects and their business impact
- Synthesize simulation predictions with empirical evidence
- Identify convergent signals across data layers
- Recommend protocol adjustments based on evidence
- Cite relevant reading from APQC best practices and TE/biofab literature

RESPONSE STYLE:
- Be concise and evidence-driven
- Reference specific lots, batches, or parameters from context
- When citing literature, use the format: [Author, Year] or [Standard Title]
- When the user states a causal claim, create a hypothesis
- When evidence supports/contradicts a hypothesis, cite it explicitly
- Flag convergent signals (simulation + empirical agreement) as high-confidence

HYPOTHESIS DETECTION:
When the user makes a causal statement like "I think X caused Y" or
"the problem is Z", wrap it in tags:
<new_hypothesis>statement here</new_hypothesis>

When the user provides evidence for or against an existing hypothesis:
<evidence for="hypothesis_id">evidence description</evidence>
<evidence against="hypothesis_id">evidence description</evidence>"""


def send_pi_message(
    context: CompanyContext,
    user_message: str,
    chat_history: Optional[list] = None,
    api_key: Optional[str] = None,
) -> dict:
    """
    Send a message to the PI chat and get a grounded response.

    Args:
        context: CompanyContext for the active company
        user_message: User's message
        chat_history: List of {"role": str, "content": str} dicts
        api_key: Optional API key override

    Returns:
        {
            "response": str,
            "new_hypotheses": list of str,
            "evidence_updates": list of {"hypothesis_id": str, "evidence": str, "direction": str},
            "context_updated": bool,
        }
    """
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from core.rag import sanitize_input

    # Sanitize input
    sanitized = sanitize_input(user_message)
    if sanitized == "I can only help with tissue engineering protocol analysis.":
        return {
            "response": sanitized,
            "new_hypotheses": [],
            "evidence_updates": [],
            "context_updated": False,
        }

    # Build messages
    system_prompt = build_pi_system_prompt(context)
    messages = [SystemMessage(content=system_prompt)]

    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=sanitized))

    # Call LLM
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.4,
        max_tokens=2048,
        api_key=key,
    )
    response = llm.invoke(messages)
    response_text = response.content

    # Extract hypothesis and evidence tags
    new_hypotheses = _extract_hypotheses(response_text)
    evidence_updates = _extract_evidence(response_text)

    # Apply to context
    context_updated = False
    for statement in new_hypotheses:
        context.add_hypothesis(statement)
        context_updated = True

    for ev in evidence_updates:
        context.update_hypothesis(ev["hypothesis_id"], ev["evidence"], ev["direction"])
        context_updated = True

    # Store in chat history
    context.pi_chat_history.append({"role": "user", "content": user_message})
    context.pi_chat_history.append({"role": "assistant", "content": response_text})

    if context_updated:
        context.save()

    # Clean tags from display text
    display_text = _clean_tags(response_text)

    return {
        "response": display_text,
        "new_hypotheses": new_hypotheses,
        "evidence_updates": evidence_updates,
        "context_updated": context_updated,
    }


def _extract_hypotheses(text: str) -> list:
    """Extract new hypothesis statements from response."""
    pattern = r"<new_hypothesis>(.*?)</new_hypothesis>"
    return re.findall(pattern, text, re.DOTALL)


def _extract_evidence(text: str) -> list:
    """Extract evidence updates from response."""
    results = []
    for_pattern = r'<evidence\s+for="([^"]+)">(.*?)</evidence>'
    against_pattern = r'<evidence\s+against="([^"]+)">(.*?)</evidence>'

    for match in re.finditer(for_pattern, text, re.DOTALL):
        results.append({
            "hypothesis_id": match.group(1),
            "evidence": match.group(2).strip(),
            "direction": "for",
        })
    for match in re.finditer(against_pattern, text, re.DOTALL):
        results.append({
            "hypothesis_id": match.group(1),
            "evidence": match.group(2).strip(),
            "direction": "against",
        })
    return results


def _clean_tags(text: str) -> str:
    """Remove hypothesis/evidence XML tags from display text."""
    text = re.sub(r"<new_hypothesis>.*?</new_hypothesis>", "", text, flags=re.DOTALL)
    text = re.sub(r'<evidence\s+(?:for|against)="[^"]*">.*?</evidence>', "", text, flags=re.DOTALL)
    return text.strip()


def _build_reading_context(context: CompanyContext) -> str:
    """Build a reading context block for the system prompt from active signals."""
    try:
        from core.reading_engine import ReadingEngine
        engine = ReadingEngine()

        # Collect signals from context
        pi_signals = set()
        for lot in context.flagged_lots:
            if lot.get("failure_mode"):
                mode = lot["failure_mode"].lower()
                if "viability" in mode:
                    pi_signals.add("viability_below_threshold")
                if "batch" in mode or "lot" in mode:
                    pi_signals.add("batch_effect")
                    pi_signals.add("lot_churn_correlation")
                if "deviation" in mode:
                    pi_signals.add("protocol_deviation")
                if "variance" in mode or "cv" in mode:
                    pi_signals.add("high_cv")

        for hyp in context.hypotheses:
            if hyp.get("status") == "open":
                stmt = hyp.get("statement", "").lower()
                if "lot" in stmt:
                    pi_signals.add("flagged_lot")
                if "batch" in stmt:
                    pi_signals.add("batch_effect")

        if not pi_signals:
            pi_signals = {"parameter_out_of_range", "conformance_failure"}

        biz = engine.get_business_reading(list(pi_signals), max_results=3)
        lines = []
        for item in biz:
            lines.append(f"- APQC {item['pcf_id']} ({item['pcf_name']}): {item['best_practice_summary'][:200]}")
            for ref in item.get("reading", [])[:1]:
                lines.append(f"  Ref: {ref.get('title', 'N/A')}")

        return "\n".join(lines) if lines else "No specific reading matched current signals."
    except Exception:
        return "Reading engine unavailable."


def get_available_companies() -> list:
    """List available company context IDs."""
    from core.company_context import CONTEXTS_DIR
    if not CONTEXTS_DIR.exists():
        return []
    return [f.stem for f in CONTEXTS_DIR.glob("*.json")]
