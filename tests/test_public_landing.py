"""The public library must work without silently starting a model conversation."""
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def public_app(monkeypatch):
    import dotenv
    import httpx
    import streamlit as st

    st.cache_data.clear()
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for name in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "VAULT_API_URL", "VAULT_API_KEY"):
        monkeypatch.setenv(name, "")
    monkeypatch.setattr(httpx, "get", Mock(side_effect=AssertionError("Unexpected network request")))
    monkeypatch.setattr(httpx, "post", Mock(side_effect=AssertionError("Unexpected model request")))
    initialize = Mock(return_value=SimpleNamespace(messages=[
        {"role": "assistant", "content": "What are you building?"}
    ]))
    chat = ModuleType("core.chat")
    chat.initialize_chat = initialize
    chat.send_message = Mock()
    chat.extract_construct_profile = Mock()
    rag = ModuleType("core.rag")
    rag.retrieve_benchmarks = Mock()
    rag.synthesize_variance_report = Mock()
    renderers = ModuleType("results_tab_renderers")
    for name in ("render_results_action_plan_tab", "render_results_feasibility_tab", "render_results_simulation_tab"):
        setattr(renderers, name, Mock())
    monkeypatch.setitem(__import__("sys").modules, "core.chat", chat)
    monkeypatch.setitem(__import__("sys").modules, "core.rag", rag)
    monkeypatch.setitem(__import__("sys").modules, "results_tab_renderers", renderers)
    source = os.environ.get("STROMALYTIX_TEST_APP", str(Path(__file__).parents[1] / "app.py"))
    app = AppTest.from_file(source, default_timeout=15)
    app.secrets = {"ANTHROPIC_API_KEY": "test-only", "OPENROUTER_API_KEY": "",
                   "VAULT_API_URL": "", "VAULT_API_KEY": ""}
    return app, initialize


def test_landing_does_not_start_model_conversation(public_app):
    app, initialize = public_app
    app.run()
    assert not app.exception
    initialize.assert_not_called()
    assert app.button(key="start_assessment").label == "Start assessment"
    assert any("reference entries" in item.value for item in app.markdown)


def test_explicit_start_initializes_once_and_preserves_conversation(public_app):
    app, initialize = public_app
    app.run()
    app.button(key="start_assessment").click().run()
    assert not app.exception
    initialize.assert_called_once()
    assert any(item.value == "What are you building?" for item in app.markdown)
    app.run()
    assert not app.exception
    initialize.assert_called_once()


def test_parameter_search_remains_available_without_model_access(public_app):
    app, initialize = public_app
    app.secrets["ANTHROPIC_API_KEY"] = ""
    app.run()
    app.text_input(key="param_search").input("oxygen").run()
    assert not app.exception
    initialize.assert_not_called()
    assert any('parameters match "oxygen"' in item.value for item in app.markdown)
    assert app.dataframe and len(app.dataframe[0].value) > 0
    assert any("Live assessment is unavailable" in item.value for item in app.info)


@pytest.mark.parametrize("status", [401, 403])
def test_public_health_does_not_hide_protocol_auth_failure(public_app, monkeypatch, status):
    import httpx

    app, initialize = public_app
    app.secrets["VAULT_API_URL"] = "https://vault.test"
    app.secrets["VAULT_API_KEY"] = "test-invalid"
    def response(url, **kwargs):
        code = 200 if url.endswith("/health") else status
        return httpx.Response(code, json={"status": "ok"}, request=httpx.Request("GET", url))
    request = Mock(side_effect=response)
    monkeypatch.setattr(httpx, "get", request)
    app.run()
    assert not app.exception
    initialize.assert_not_called()
    assert request.called
    assert any("Protocol search: **Unavailable in this session**" in item.value for item in app.markdown)
    assert any("Live protocol search is unavailable" in item.value for item in app.warning)
    assert any(item.url.endswith("#demo") for item in app.get("link_button"))


@pytest.mark.parametrize("browse_status", [200, 503])
def test_empty_protocol_response_and_later_failure_are_distinct(public_app, monkeypatch, browse_status):
    import httpx

    app, _ = public_app
    app.secrets["VAULT_API_URL"] = "https://vault.test"
    app.secrets["VAULT_API_KEY"] = "test-only"
    def response(url, **kwargs):
        is_browse = (kwargs.get("params") or {}).get("limit") != 1
        code = browse_status if is_browse and url.endswith("/protocols") else 200
        payload = {"total_protocols": 0} if url.endswith("/stats") else {"protocols": [], "total": 0}
        return httpx.Response(code, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", Mock(side_effect=response))
    app.run()
    assert not app.exception
    if browse_status == 200:
        assert any("No protocols match" in item.value for item in app.info)
        assert not any("Live protocol search is unavailable" in item.value for item in app.warning)
    else:
        assert any("Live protocol search is unavailable" in item.value for item in app.warning)
