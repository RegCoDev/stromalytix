"""Tests for PI Chat — context-grounded conversational analyst."""


def test_pi_chat_importable():
    from core.pi_chat import build_pi_system_prompt, send_pi_message, get_available_companies
    assert build_pi_system_prompt is not None
    assert send_pi_message is not None
    assert get_available_companies is not None


def test_build_pi_system_prompt_includes_company_context():
    from core.company_context import CompanyContext
    from core.pi_chat import build_pi_system_prompt

    ctx = CompanyContext(
        company_id="t", company_name="TestCo",
        industry_segment="pharma",
        biofab_methods=["bioprinting"],
        flagged_lots=[{"lot_id": "LOT-X", "issue": "low viability"}],
    )
    prompt = build_pi_system_prompt(ctx)
    assert "TestCo" in prompt
    assert "pharma" in prompt
    assert "bioprinting" in prompt
    assert "LOT-X" in prompt
    assert "Process Intelligence Analyst" in prompt


def test_build_pi_system_prompt_includes_hypotheses():
    from core.company_context import CompanyContext
    from core.pi_chat import build_pi_system_prompt

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.add_hypothesis("GelMA batch caused failure")
    prompt = build_pi_system_prompt(ctx)
    assert "GelMA batch caused failure" in prompt


def test_extract_hypotheses():
    from core.pi_chat import _extract_hypotheses

    text = "I see. <new_hypothesis>LOT-B2 caused viability drop</new_hypothesis> Let me check."
    hyps = _extract_hypotheses(text)
    assert len(hyps) == 1
    assert "LOT-B2" in hyps[0]


def test_extract_evidence_for_and_against():
    from core.pi_chat import _extract_evidence

    text = (
        '<evidence for="hyp_01">CV matches B2 timeline</evidence>'
        '<evidence against="hyp_01">Temperature also changed</evidence>'
    )
    evs = _extract_evidence(text)
    assert len(evs) == 2
    assert evs[0]["direction"] == "for"
    assert evs[1]["direction"] == "against"
    assert evs[0]["hypothesis_id"] == "hyp_01"


def test_clean_tags_removes_hypothesis_and_evidence():
    from core.pi_chat import _clean_tags

    text = (
        "Analysis shows issue. "
        "<new_hypothesis>B2 is root cause</new_hypothesis> "
        '<evidence for="h1">data supports</evidence>'
        "That's what I found."
    )
    cleaned = _clean_tags(text)
    assert "<new_hypothesis>" not in cleaned
    assert "<evidence" not in cleaned
    assert "Analysis shows issue" in cleaned
    assert "That's what I found" in cleaned


def test_get_available_companies_returns_list():
    from core.pi_chat import get_available_companies

    companies = get_available_companies()
    assert isinstance(companies, list)
    # centara_demo should exist from previous test/creation
    # but don't assert content since test order isn't guaranteed


def test_centara_context_prompt_has_flagged_lots():
    from core.company_context import create_centara_demo_context
    from core.pi_chat import build_pi_system_prompt
    from pathlib import Path

    ctx = create_centara_demo_context()
    prompt = build_pi_system_prompt(ctx)
    assert "LOT-2024-B2" in prompt
    assert "LOT-2025-B1" in prompt
    assert "Centara" in prompt
    # Cleanup
    Path("data/company_contexts/centara_demo.json").unlink(missing_ok=True)
