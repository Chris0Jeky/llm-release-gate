"""Unreadable and unparseable inputs fail as named configuration errors."""

import builtins
import errno
import json
import sys

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import _load_json_file
from llm_release_gate.providers import build_provider

from conftest import gate_argv


@pytest.mark.parametrize("target", ["dataset", "fixture"])
@pytest.mark.parametrize("failure", ["permission", "disappeared", "read"])
def test_input_os_errors_are_config_errors(tmp_path, monkeypatch, target, failure):
    path = tmp_path / "input.json"
    path.write_text("{}", encoding="utf-8")
    real_open = builtins.open
    code = errno.ENOENT if failure == "disappeared" else errno.EACCES
    expected = "not found" if failure == "disappeared" else "could not be read"

    class BrokenReader:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            raise OSError(errno.EIO, "synthetic read failure")

    def failing_open(name, *args, **kwargs):
        if str(name) == str(path):
            if failure == "read":
                return BrokenReader()
            raise OSError(code, "synthetic open failure", str(path))
        return real_open(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", failing_open)
    with pytest.raises(GateConfigError, match=expected) as excinfo:
        if target == "dataset":
            _load_json_file(str(path), "dataset")
        else:
            build_provider("fake", {"fixtures": str(path)}, str(tmp_path))
    assert str(path) in str(excinfo.value)
    assert ("dataset" if target == "dataset" else "fake provider") in str(excinfo.value)


@pytest.mark.parametrize("target", ["dataset", "fixture"])
def test_directory_input_is_named_config_error(tmp_path, target):
    with pytest.raises(GateConfigError) as excinfo:
        if target == "dataset":
            _load_json_file(str(tmp_path), "dataset")
        else:
            build_provider("fake", {"fixtures": str(tmp_path)}, str(tmp_path))
    assert str(tmp_path) in str(excinfo.value)


@pytest.mark.parametrize("bad", [True, 1, ["fx.json"], {"path": "fx.json"}])
def test_fixture_path_must_be_a_string(tmp_path, bad):
    with pytest.raises(GateConfigError, match="provider_options.fixtures"):
        build_provider("fake", {"fixtures": bad}, str(tmp_path))


@pytest.mark.parametrize("target", ["dataset", "fixture"])
@pytest.mark.parametrize("source,diagnostic", [
    (b'{"bad": "\xff"}', "not valid UTF-8"),
    (b'{"bad": }', "not valid JSON"),
])
def test_malformed_input_is_clean_cli_error(mini_gate, capsys, target, source, diagnostic):
    paths = mini_gate()
    path = paths["tmp"] / ("dataset.json" if target == "dataset" else "fixtures/candidate.json")
    path.write_bytes(source)
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "configuration error" in err
    assert diagnostic in err
    assert str(path).replace("\\", "/") in err.replace("\\", "/")
    assert "Traceback" not in err
    assert not (paths["tmp"] / "out" / "report.json").exists()


@pytest.mark.parametrize("target", ["dataset", "fixture"])
def test_json_integer_digit_limit_is_clean_cli_error(mini_gate, capsys, target):
    limit = sys.get_int_max_str_digits()
    if not limit:
        pytest.skip("interpreter's integer digit limit is disabled")
    paths = mini_gate()
    path = paths["tmp"] / ("dataset.json" if target == "dataset" else "fixtures/candidate.json")
    path.write_text('{"unused": ' + "1" * (limit + 1) + '}', encoding="utf-8")
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "configuration error" in err
    assert "JSON" in err
    assert str(path).replace("\\", "/") in err.replace("\\", "/")
    assert "Traceback" not in err
    assert not (paths["tmp"] / "out" / "report.json").exists()


@pytest.mark.parametrize("target", ["dataset", "fixture"])
def test_parser_recursion_limit_is_named_config_error(tmp_path, monkeypatch, target):
    # Decoder nesting limits vary across supported interpreters; simulate the
    # exception without requiring a particular stack limit or JSON depth.
    path = tmp_path / "deep.json"
    path.write_text("[[]]", encoding="utf-8")

    def nesting_limit(*args, **kwargs):
        raise RecursionError("synthetic JSON nesting limit")

    monkeypatch.setattr(json, "loads", nesting_limit)
    with pytest.raises(GateConfigError, match="nesting") as excinfo:
        if target == "dataset":
            _load_json_file(str(path), "dataset")
        else:
            build_provider("fake", {"fixtures": str(path)}, str(tmp_path))
    assert str(path) in str(excinfo.value)
