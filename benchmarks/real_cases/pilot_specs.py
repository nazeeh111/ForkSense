"""Predeclared agent-visible contracts derived only from issue text/base source.

These smoke checks deliberately do not encode the external official evaluator's
extra API/exception/header requirements. They are repair feedback, not final
resolution evidence. Freeze this file's hash before the first live attempt.
"""
from __future__ import annotations

import copy
import textwrap


def code(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


BLUEPRINT_SMOKE = code('''
    import flask

    # The issue requests an error for a dotted blueprint name, without
    # specifying its concrete exception class.
    rejected = False
    try:
        flask.Blueprint("section.child", "public_smoke", root_path=".")
    except Exception:
        rejected = True
    assert rejected, "A dotted blueprint name must be rejected during construction"

    app = flask.Flask("public_smoke", root_path=".")
    plain = flask.Blueprint("section", "public_smoke", root_path=".")
    plain.add_url_rule("/hello", endpoint="hello", view_func=lambda: "hello")
    app.register_blueprint(plain)
    response = app.test_client().get("/hello")
    assert response.status_code == 200 and response.data == b"hello"
    print("public issue smoke passed")
''')

ROUTES_SMOKE = code('''
    import flask
    from click.testing import CliRunner
    from flask.cli import FlaskGroup

    app = flask.Flask("public_smoke", root_path=".", static_folder=None)
    app.config["SERVER_NAME"] = "test.local"
    admin = flask.Blueprint("alpha_group", "public_smoke", root_path=".")
    other = flask.Blueprint("beta_group", "public_smoke", root_path=".")
    admin.add_url_rule("/dashboard", endpoint="alpha_view", view_func=lambda: "a")
    other.add_url_rule("/metrics", endpoint="beta_view", view_func=lambda: "b")
    app.register_blueprint(admin, subdomain="admin")
    app.register_blueprint(other, subdomain="test")
    result = CliRunner().invoke(FlaskGroup(create_app=lambda: app), ["routes"])
    assert result.exit_code == 0, repr(result.exception)
    output = result.output
    assert "admin" in output and "test" in output, output
    assert "/dashboard" in output and "/metrics" in output and "GET" in output, output
    # The issue permits a domain or subdomain display; no particular header,
    # formatting, sorting mode, or host-matching behavior is required here.
    print("public issue smoke passed")
''')

BLUEPRINT_PROBES = [
    {
        "id": "dotted-construction-rejected",
        "label": "Does construction itself reject dotted names?",
        "source": code('''
            import flask
            try:
                flask.Blueprint("area.view", "probe", root_path=".")
            except Exception:
                print("construction rejected dotted name")
            else:
                raise AssertionError("construction accepted dotted name")
        '''),
    },
    {
        "id": "ordinary-blueprint-works",
        "label": "Can a plain blueprint still register a route?",
        "source": code('''
            import flask
            app = flask.Flask("probe", root_path=".")
            bp = flask.Blueprint("area", "probe", root_path=".")
            bp.add_url_rule("/ok", endpoint="show", view_func=lambda: "ok")
            app.register_blueprint(bp)
            assert app.test_client().get("/ok").data == b"ok"
            print("ordinary blueprint works")
        '''),
    },
]

ROUTES_PROBES = [
    {
        "id": "direct-rule-has-subdomain",
        "label": "Does routing retain a directly declared subdomain?",
        "source": code('''
            import flask
            app = flask.Flask("probe", root_path=".", static_folder=None)
            app.add_url_rule("/x", endpoint="item", subdomain="admin")
            rule = next(app.url_map.iter_rules())
            assert rule.subdomain == "admin", repr(rule.subdomain)
            print("direct rule retains subdomain")
        '''),
    },
    {
        "id": "blueprint-rule-has-subdomain",
        "label": "Does blueprint registration retain its subdomain?",
        "source": code('''
            import flask
            app = flask.Flask("probe", root_path=".", static_folder=None)
            bp = flask.Blueprint("alpha_group", "probe", root_path=".")
            bp.add_url_rule("/x", endpoint="item")
            app.register_blueprint(bp, subdomain="admin")
            rule = next(app.url_map.iter_rules())
            assert rule.subdomain == "admin", repr(rule.subdomain)
            print("blueprint rule retains subdomain")
        '''),
    },
    {
        "id": "routes-displays-subdomain",
        "label": "Does routes display retained subdomain information?",
        "source": code('''
            import flask
            from click.testing import CliRunner
            from flask.cli import FlaskGroup
            app = flask.Flask("probe", root_path=".", static_folder=None)
            app.add_url_rule("/x", endpoint="item", subdomain="admin")
            result = CliRunner().invoke(FlaskGroup(create_app=lambda: app), ["routes"])
            assert result.exit_code == 0, repr(result.exception)
            assert "admin" in result.output, result.output
            print("routes displays subdomain")
        '''),
    },
]

SPECS = {
    "pallets__flask-4045": {
        "base_commit": "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0",
        "source_issue": "https://github.com/pallets/flask/issues/4041",
        "editable_paths": ["src/flask"],
        "public_contract": "Reject blueprint names containing a dot at construction, while ordinary blueprint creation, registration and routing remain usable. The issue does not prescribe a concrete exception class.",
        "smoke_source": BLUEPRINT_SMOKE,
        "probes": BLUEPRINT_PROBES,
    },
    "pallets__flask-5063": {
        "base_commit": "182ce3dd15dfa3537391c3efaf9c3ff407d134d4",
        "source_issue": "https://github.com/pallets/flask/issues/5004",
        "editable_paths": ["src/flask"],
        "public_contract": "Display each route's domain or subdomain in flask routes so developers can distinguish blueprint routes assigned to admin and test subdomains. Preserve the route path and methods. The issue does not require a particular column header or host-matching behavior.",
        "smoke_source": ROUTES_SMOKE,
        "probes": ROUTES_PROBES,
    },
}


def case_spec(instance_id: str, python: str) -> dict:
    """Return public repair feedback/probes; a planner supplies hypotheses.

    The caller sets PYTHONPATH to the candidate's src directory. Commands use
    ordinary argv and inherit existing agent sandbox permissions.
    """
    spec = copy.deepcopy(SPECS[instance_id])
    spec["instance_id"] = instance_id
    spec["verify"] = [python, "-W", "ignore::DeprecationWarning", "-c", spec["smoke_source"]]
    for probe in spec["probes"]:
        probe["command"] = [python, "-W", "ignore::DeprecationWarning", "-c", probe["source"]]
    return spec
