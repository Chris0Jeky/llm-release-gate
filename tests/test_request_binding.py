"""Replay binding checks the request, not just its model/item lookup key."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from conftest import gate_argv
from llm_release_gate.adapters import build_adapter
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.hashing import content_hash
from llm_release_gate.loading import load_dataset, load_run_config
from llm_release_gate.providers import ProviderRequest, build_provider


def reference_hash(request):
    return content_hash({"schema_version": "lrg-provider-request/1",
                         "model": request.model, "system": request.system,
                         "prompt": request.prompt, "params": request.params,
                         "item_id": request.item_id, "metadata": request.metadata})


def binding_module():
    assert importlib.util.find_spec("llm_release_gate.requests") is not None
    from llm_release_gate import requests
    return requests


def bind_fixture(paths, role):
    path = Path(paths[role])
    data = json.loads(path.read_text())
    data["provider_options"]["request_binding"] = "sha256-v1"
    path.write_text(json.dumps(data))
    dataset, config = load_dataset(paths["dataset"]), load_run_config(str(path), role)
    fixture = path.parent / config.provider_options["fixtures"]
    raw = json.loads(fixture.read_text())
    adapter = build_adapter(dataset.task)
    for item in dataset.items:
        entry = raw["responses"][config.model][item.id]
        entry["request_sha256"] = reference_hash(adapter.build_request(item, config))
    fixture.write_text(json.dumps(raw))
    return fixture


@pytest.mark.parametrize("field,value", [("model", "other"), ("system", "other"),
    ("prompt", "other"), ("params", {"temperature": 0.2}), ("item_id", "other"),
    ("metadata", {"endpoint": "other"})])
def test_fingerprint_covers_every_request_field(field, value):
    mod = binding_module()
    request = ProviderRequest(model="m", system="system", prompt="prompt", params={}, item_id="i")
    expected = reference_hash(request)
    assert mod.request_fingerprint(request) == expected
    setattr(request, field, value)
    assert mod.request_fingerprint(request) != expected


def test_fingerprint_ignores_object_key_order_not_value_types():
    mod = binding_module()
    request = ProviderRequest("m", "s", "é", {"z": 0, "a": 1}, "i")
    first = mod.request_fingerprint(request)
    request.params = {"a": 1, "z": 0}
    assert mod.request_fingerprint(request) == first
    request.params["a"] = True
    assert mod.request_fingerprint(request) != first


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object(), {1: "value"}, (1, 2)])
def test_invalid_request_values_fail_without_echoing_sensitive_prompt(bad):
    mod = binding_module()
    request = ProviderRequest("m", "SECRET-SYSTEM", "SECRET-PROMPT", {"value": bad}, "i")
    with pytest.raises(GateConfigError) as exc:
        mod.request_fingerprint(request)
    assert "request" in str(exc.value)
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize("binding", [None, True, False, "", "sha256-v2", {}])
def test_unknown_explicit_binding_mode_fails_closed(mini_gate, binding):
    paths = mini_gate()
    with pytest.raises(GateConfigError, match="request_binding"):
        build_provider("fake", {"fixtures": "fixtures/candidate.json", "request_binding": binding},
                       str(paths["tmp"]))


@pytest.mark.parametrize("mutation", ["template", "system", "params", "question", "document", "model"])
def test_stale_fixture_is_configuration_error_even_under_permissive_policy(mini_gate, mutation, capsys):
    paths = mini_gate(thresholds={"rules": [{"metric": "errors.error_rate", "max_value": 1.0}]})
    bind_fixture(paths, "baseline")
    bind_fixture(paths, "candidate")
    cfg = json.loads(Path(paths["candidate"]).read_text())
    dataset = json.loads(Path(paths["dataset"]).read_text())
    if mutation in ("template", "system"):
        cfg["prompt"][mutation] += " CHANGED"
    elif mutation == "params":
        cfg["params"] = {"temperature": 0.9}
    elif mutation == "model":
        cfg["model"] = "different-model"
    elif mutation == "question":
        dataset["items"][0]["input"]["question"] += " CHANGED"
    else:
        dataset["items"][0]["input"]["documents"][0]["text"] += " CHANGED"
    Path(paths["candidate"]).write_text(json.dumps(cfg))
    Path(paths["dataset"]).write_text(json.dumps(dataset))
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "request binding" in err
    assert "Traceback" not in err
    assert not Path(paths["out"]).exists()


@pytest.mark.parametrize("digest", [None, "sha256:" + "0" * 64, "sha256:" + "A" * 64, 42, "bad"])
def test_missing_invalid_or_wrong_fixture_digest_refused(mini_gate, digest, capsys):
    paths = mini_gate()
    fixture = bind_fixture(paths, "candidate")
    data = json.loads(fixture.read_text())
    entry = data["responses"]["m-cand"]["r1"]
    if digest is None:
        del entry["request_sha256"]
    else:
        entry["request_sha256"] = digest
    fixture.write_text(json.dumps(data))
    assert main(gate_argv(paths)) == 2
    assert "request binding" in capsys.readouterr().err
    assert not Path(paths["out"]).exists()


def test_missing_bound_item_cannot_be_warned_away(mini_gate):
    paths = mini_gate(thresholds={"rules": [{"metric": "errors.error_rate", "max_value": 1.0}]})
    fixture = bind_fixture(paths, "candidate")
    data = json.loads(fixture.read_text())
    del data["responses"]["m-cand"]["r1"]
    fixture.write_text(json.dumps(data))
    assert main(gate_argv(paths)) == 2


def test_error_fixture_must_be_bound_before_provider_failure(mini_gate):
    paths = mini_gate(thresholds={"rules": [{"metric": "errors.error_rate", "max_value": 1.0}]})
    fixture = bind_fixture(paths, "candidate")
    data = json.loads(fixture.read_text())
    data["responses"]["m-cand"]["r1"] = {"error": "unbound outage"}
    fixture.write_text(json.dumps(data))
    assert main(gate_argv(paths)) == 2


def test_valid_bound_replay_still_passes_and_discloses_mode(mini_gate):
    paths = mini_gate()
    bind_fixture(paths, "baseline")
    bind_fixture(paths, "candidate")
    assert main(gate_argv(paths)) == 0
    report = json.loads((Path(paths["out"]) / "report.json").read_text())
    for role in ("baseline", "candidate"):
        assert report["runs"][role]["provider"]["request_binding"] == "sha256-v1"


def test_legacy_mode_does_not_claim_binding(mini_gate):
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    report = json.loads((Path(paths["out"]) / "report.json").read_text())
    assert "request_binding" not in report["runs"]["candidate"]["provider"]


def plan_args(paths, out):
    return ["plan", "--dataset", paths["dataset"], "--config", paths["candidate"], "--out", str(out)]


def test_plan_works_without_provider_or_fixture_and_has_no_raw_prompts(mini_gate, monkeypatch):
    paths = mini_gate()
    fixture = paths["tmp"] / "fixtures/candidate.json"
    fixture.unlink()
    from llm_release_gate.providers.fake import FakeProvider
    def forbidden(*a, **kw):
        pytest.fail("planning constructed a provider")
    monkeypatch.setattr(FakeProvider, "__init__", forbidden)
    out = paths["tmp"] / "planning"
    assert main(plan_args(paths, out)) == 0
    plan = json.loads((out / "plan.json").read_text())
    assert plan["schema_version"] == "lrg-request-plan/1"
    digest = plan.pop("plan_hash")
    assert content_hash(plan) == digest
    assert [item["item_id"] for item in plan["requests"]] == ["r1", "r2", "r3"]
    cfg, dataset = load_run_config(paths["candidate"], "config"), load_dataset(paths["dataset"])
    adapter = build_adapter(dataset.task)
    assert plan["requests"][0]["request_sha256"] == reference_hash(adapter.build_request(dataset.items[0], cfg))
    text = (out / "plan.json").read_text()
    assert "What color is the sky" not in text
    assert str(paths["tmp"]) not in text
    assert "gate" not in plan


def test_plan_deterministic_and_non_overwriting(mini_gate, capsys):
    paths = mini_gate()
    out1, out2 = paths["tmp"] / "one", paths["tmp"] / "two"
    assert main(plan_args(paths, out1)) == 0
    expected = (out1 / "plan.json").read_bytes()
    assert main(plan_args(paths, out2)) == 0
    assert (out2 / "plan.json").read_bytes() == expected
    assert main(plan_args(paths, out1)) == 2
    assert (out1 / "plan.json").read_bytes() == expected
    assert "Traceback" not in capsys.readouterr().err


def test_plan_limit_and_bad_template_fail_without_output(mini_gate):
    paths = mini_gate()
    out = paths["tmp"] / "planning"
    assert main(plan_args(paths, out) + ["--max-input-bytes", "1"]) == 2
    assert not out.exists()
    cfg = json.loads(Path(paths["candidate"]).read_text())
    cfg["prompt"]["template"] = "$undefined"
    Path(paths["candidate"]).write_text(json.dumps(cfg))
    assert main(plan_args(paths, out)) == 2
    assert not out.exists()


@pytest.mark.parametrize("role", ["baseline", "candidate"])
def test_required_binding_refuses_config_downgrade(mini_gate, role, capsys):
    paths = mini_gate()
    bind_fixture(paths, "baseline")
    bind_fixture(paths, "candidate")
    config = json.loads(Path(paths[role]).read_text())
    del config["provider_options"]["request_binding"]
    Path(paths[role]).write_text(json.dumps(config))
    assert main(gate_argv(paths) + ["--require-request-binding"]) == 2
    assert "requires fake provider request_binding='sha256-v1'" in capsys.readouterr().err
    assert not Path(paths["out"]).exists()


def test_required_binding_receipt_composes_with_byte_limit(mini_gate):
    paths = mini_gate()
    bind_fixture(paths, "baseline")
    bind_fixture(paths, "candidate")
    assert main(gate_argv(paths)) == 0
    before = (Path(paths["out"]) / "report.json").read_bytes()
    assert main(gate_argv(paths) + ["--require-request-binding", "--max-input-bytes", "100000"]) == 0
    assert (Path(paths["out"]) / "report.json").read_bytes() == before
    manifest = json.loads((Path(paths["out"]) / "manifest.json").read_text())
    assert manifest["execution_options"] == {"require_request_binding": True, "max_input_bytes": 100000}


def test_required_binding_applies_to_run(mini_gate):
    paths = mini_gate()
    argv = ["run", "--dataset", paths["dataset"], "--config", paths["candidate"],
            "--scorers", paths["scorers"], "--out", paths["out"], "--require-request-binding"]
    assert main(argv) == 2
    bind_fixture(paths, "candidate")
    assert main(argv + ["--fail-on-errors"]) == 0


@pytest.mark.parametrize("version", [None, 1, True, "2", "1.0"])
def test_bound_fixture_requires_known_version(mini_gate, version, capsys):
    paths = mini_gate()
    fixture = bind_fixture(paths, "candidate")
    data = json.loads(fixture.read_text())
    data["version"] = version
    fixture.write_text(json.dumps(data))
    assert main(gate_argv(paths)) == 2
    assert "request binding requires fixture version '1'" in capsys.readouterr().err
    assert not Path(paths["out"]).exists()


@pytest.mark.parametrize("permissive,expected", [(False, 1), (True, 0)])
def test_bound_provider_errors_retain_existing_policy(mini_gate, permissive, expected):
    rules = {"rules": [{"metric": "errors.error_rate", "max_value": 1}]} if permissive else None
    paths = mini_gate(thresholds=rules)
    bind_fixture(paths, "baseline")
    fixture = bind_fixture(paths, "candidate")
    data = json.loads(fixture.read_text())
    entry = data["responses"]["m-cand"]["r1"]
    data["responses"]["m-cand"]["r1"] = {"request_sha256": entry["request_sha256"], "error": "outage"}
    fixture.write_text(json.dumps(data))
    assert main(gate_argv(paths)) == expected
    report = json.loads((Path(paths["out"]) / "report.json").read_text())
    assert report["runs"]["candidate"]["n_errors"] == 1


def test_binding_identifies_requests_not_expectations_or_file_layout(mini_gate):
    from llm_release_gate.planning import build_request_plan
    paths = mini_gate()
    def plan():
        return build_request_plan(load_dataset(paths["dataset"]), load_run_config(paths["candidate"], "config"))
    first = plan()
    dataset = json.loads(Path(paths["dataset"]).read_text())
    dataset["items"][0]["expected"]["quality"]["must_contain"] = ["new expectation"]
    Path(paths["dataset"]).write_text(json.dumps(dataset, indent=4))
    second = plan()
    assert second["requests"] == first["requests"]
    assert second["plan_hash"] != first["plan_hash"]
    data = Path(paths["dataset"]).read_bytes()
    Path(paths["dataset"]).write_bytes(data.replace(b"\n", b"\r\n"))
    assert plan() == second


def test_relocation_does_not_change_plan(mini_gate, tmp_path):
    from llm_release_gate.planning import build_request_plan
    paths = mini_gate()
    first = build_request_plan(load_dataset(paths["dataset"]), load_run_config(paths["candidate"], "config"))
    relocated = tmp_path / "relocated"
    relocated.mkdir()
    for key in ("dataset", "candidate"):
        shutil.copyfile(paths[key], relocated / f"{key}.json")
    second = build_request_plan(load_dataset(str(relocated / "dataset.json")),
                                load_run_config(str(relocated / "candidate.json"), "config"))
    assert first == second


def test_plan_cannot_overwrite_its_input(mini_gate, capsys):
    paths = mini_gate()
    source = paths["tmp"] / "plan.json"
    source.write_bytes(Path(paths["dataset"]).read_bytes())
    before = source.read_bytes()
    paths["dataset"] = str(source)
    assert main(plan_args(paths, source.parent)) == 2
    assert source.read_bytes() == before
    assert "Traceback" not in capsys.readouterr().err


def test_cyclic_or_surrogate_request_is_clean_configuration_error():
    mod = binding_module()
    cyclic = {}
    cyclic["self"] = cyclic
    for value in (cyclic, "\ud800"):
        request = ProviderRequest("m", "secret", "secret", {"bad": value}, "i")
        with pytest.raises(GateConfigError):
            mod.request_fingerprint(request)


def test_action_can_require_binding_independently_of_candidate_config():
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text()
    assert 'IN_REQUIRE_BINDING: ${{ inputs.require-request-binding }}' in action
    assert 'true) args+=(--require-request-binding)' in action
    assert '"cli-exit=2"' in action


@pytest.mark.parametrize("roles", [("candidate",), ("baseline", "candidate")])
def test_bound_reports_disclose_assurance_limit_in_all_formats(mini_gate, roles):
    paths = mini_gate()
    for role in roles:
        bind_fixture(paths, role)
    assert main(gate_argv(paths)) == 0
    for suffix in ("json", "md", "html"):
        report = (Path(paths["out"]) / ("report." + suffix)).read_text()
        assert "Request-bound replay" in report
        assert "not attest model execution or producer authenticity" in report


def test_invalid_plan_metadata_is_named_config_error_not_traceback(mini_gate, capsys):
    paths = mini_gate()
    config = json.loads(Path(paths["candidate"]).read_text())
    config["provider"] = "\ud800"
    Path(paths["candidate"]).write_text(json.dumps(config))
    out = paths["tmp"] / "invalid-plan"
    assert main(plan_args(paths, out)) == 2
    error = capsys.readouterr().err
    assert "configuration error" in error
    assert "Traceback" not in error
    assert not out.exists()


def test_versioned_fingerprint_has_fixed_utf8_preimage():
    import hashlib
    # Independently specified canonical bytes; do not reuse hashing.canonical_json.
    canonical = ('{"item_id":"i","metadata":{},"model":"m","params":{"temperature":0},'
                 '"prompt":"café","schema_version":"lrg-provider-request/1","system":"s"}')
    request = ProviderRequest("m", "s", "café", {"temperature": 0}, "i")
    assert binding_module().request_fingerprint(request) == "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
