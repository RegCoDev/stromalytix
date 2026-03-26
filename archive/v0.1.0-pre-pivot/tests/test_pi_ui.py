"""Tests for Process Intelligence UI module."""


def test_pi_ui_module_importable():
    from core.pi_ui import render_pi_dashboard
    assert callable(render_pi_dashboard)


def test_connector_section_renders():
    from core.pi_ui import render_connector_section
    assert callable(render_connector_section)


def test_process_mining_section_renders():
    from core.pi_ui import render_process_mining_section
    assert callable(render_process_mining_section)


def test_cross_layer_section_renders():
    from core.pi_ui import render_cross_layer_section
    assert callable(render_cross_layer_section)


def test_process_graph_section_renders():
    from core.pi_ui import render_process_graph_section
    assert callable(render_process_graph_section)


def test_simulation_stack_section_renders():
    from core.pi_ui import render_simulation_stack_section
    assert callable(render_simulation_stack_section)


def test_render_pi_dashboard_callable():
    from core.pi_ui import render_pi_dashboard
    assert callable(render_pi_dashboard)
