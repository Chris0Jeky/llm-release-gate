"""Per-item isolation: one malformed item must not abort the whole run."""

from __future__ import annotations

import json


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_malformed_middle_item_records_error_and_continues(tmp_path):
    from llm_release_gate.loading import (
        load_dataset,
        load_run_config,
        load_scorer_config,
        no_pricing,
    )
    from llm_release_gate.runner import run_config
    from llm_release_gate.scorers import build_scorers

    dataset_doc = {
        "name": "d",
        "version": "1",
        "task": "rag",
        "items": [
            {
                "id": "r1",
                "input": {
                    "question": "What color is the sky?",
                    "documents": [{"id": "s1", "text": "The sky is blue."}],
                },
                "expected": {
                    "should_abstain": False,
                    "quality": {"must_contain": ["blue"]},
                    "must_cite": ["s1"],
                },
            },
            {
                "id": "r2",
                "input": {
                    "question": "What is the capital of Freedonia?",
                    "documents": [
                        {"id": "s1", "text": "The capital of Freedonia is Fredville."}
                    ],
                },
                "expected": {
                    "should_abstain": False,
                    "quality": {"must_contain": ["fredville"]},
                    "must_cite": ["s1"],
                },
            },
            {
                "id": "r3",
                "input": {
                    "question": "What color is the ocean?",
                    "documents": [{"id": "s1", "text": "The ocean is blue."}],
                },
                "expected": {
                    "should_abstain": False,
                    "quality": {"must_contain": ["blue"]},
                    "must_cite": ["s1"],
                },
            },
        ],
    }
    dataset = load_dataset(_write(tmp_path / "dataset.json", dataset_doc))

    # Middle item's fixture text is a JSON number, not a string. It passes
    # fixture validation and reaches adapter.parse, where the old code raised
    # TypeError outside the ProviderError try and aborted the run with no report.
    _write(tmp_path / "fx.json", {
        "version": "1",
        "responses": {
            "m": {
                "r1": {"text": "The sky is blue. [doc:s1]"},
                "r2": {"text": 123},
                "r3": {"text": "The ocean is blue. [doc:s1]"},
            }
        },
    })
    config = load_run_config(_write(tmp_path / "cand.json", {
        "name": "candidate",
        "provider": "fake",
        "model": "m",
        "prompt": {"system": "", "template": "$question"},
        "provider_options": {"fixtures": "fx.json"},
    }), "candidate")
    scorers = build_scorers(load_scorer_config(_write(tmp_path / "scorers.json", {
        "scorers": [{"type": "keyword_quality"}],
    })))

    result = run_config(dataset, config, scorers, no_pricing())

    assert result.n_items == 3
    assert result.n_ok == 2
    assert result.n_errors == 1
    by_id = {r.item_id: r for r in result.records}
    assert by_id["r2"].status == "error"
    assert by_id["r2"].error
    assert by_id["r1"].status == "ok"
    assert by_id["r3"].status == "ok"
    # Aggregates still produced over the surviving items.
    assert result.aggregates["errors.error_rate"]["available"] is True
    assert result.aggregates["errors.error_rate"]["value"] == 1 / 3
    assert result.aggregates["quality.pass_rate"]["available"] is True


def _rag_item(item_id, question, doc_text, must_contain):
    return {
        "id": item_id,
        "input": {
            "question": question,
            "documents": [{"id": "s1", "text": doc_text}],
        },
        "expected": {
            "should_abstain": False,
            "quality": {"must_contain": [must_contain]},
            "must_cite": ["s1"],
        },
    }


def _run_two_item_gate(tmp_path, responses):
    from llm_release_gate.loading import (
        load_dataset,
        load_run_config,
        load_scorer_config,
        no_pricing,
    )
    from llm_release_gate.runner import run_config
    from llm_release_gate.scorers import build_scorers

    dataset_doc = {
        "name": "d",
        "version": "1",
        "task": "rag",
        "items": [
            _rag_item("i1", "What color is the sky?", "The sky is blue.", "blue"),
            _rag_item(
                "i2",
                "What color is the ocean?",
                "The ocean is blue.",
                "blue",
            ),
        ],
    }
    dataset = load_dataset(_write(tmp_path / "dataset.json", dataset_doc))
    _write(tmp_path / "fx.json", {"version": "1", "responses": responses})
    config = load_run_config(_write(tmp_path / "cand.json", {
        "name": "candidate",
        "provider": "fake",
        "model": "m",
        "prompt": {"system": "", "template": "$question"},
        "provider_options": {"fixtures": "fx.json"},
    }), "candidate")
    scorers = build_scorers(load_scorer_config(_write(tmp_path / "scorers.json", {
        "scorers": [{"type": "keyword_quality"}],
    })))
    return run_config(dataset, config, scorers, no_pricing())


def test_non_string_fixture_text_is_per_item_error_and_continues(tmp_path):
    result = _run_two_item_gate(tmp_path, {
        "m": {
            "i1": {"text": 123},
            "i2": {"text": "The ocean is blue. [doc:s1]"},
        }
    })

    assert result.n_items == 2
    assert result.n_ok == 1
    assert result.n_errors == 1
    by_id = {r.item_id: r for r in result.records}
    assert by_id["i1"].status == "error"
    assert by_id["i1"].error
    assert "i1" in by_id["i1"].error
    assert "m" in by_id["i1"].error
    assert "non-string" in by_id["i1"].error
    assert by_id["i2"].status == "ok"
    assert result.aggregates["errors.error_rate"]["value"] == 1 / 2


def test_null_and_list_fixture_text_are_per_item_errors(tmp_path):
    from llm_release_gate.loading import (
        load_dataset,
        load_run_config,
        load_scorer_config,
        no_pricing,
    )
    from llm_release_gate.runner import run_config
    from llm_release_gate.scorers import build_scorers

    dataset_doc = {
        "name": "d",
        "version": "1",
        "task": "rag",
        "items": [
            _rag_item("i1", "What color is the sky?", "The sky is blue.", "blue"),
            _rag_item(
                "i2",
                "What is the capital of Freedonia?",
                "The capital of Freedonia is Fredville.",
                "fredville",
            ),
            _rag_item(
                "i3",
                "What color is the ocean?",
                "The ocean is blue.",
                "blue",
            ),
        ],
    }
    dataset = load_dataset(_write(tmp_path / "dataset.json", dataset_doc))
    _write(tmp_path / "fx.json", {
        "version": "1",
        "responses": {
            "m": {
                "i1": {"text": None},
                "i2": {"text": ["The capital of Freedonia is Fredville."]},
                "i3": {"text": "The ocean is blue. [doc:s1]"},
            }
        },
    })
    config = load_run_config(_write(tmp_path / "cand.json", {
        "name": "candidate",
        "provider": "fake",
        "model": "m",
        "prompt": {"system": "", "template": "$question"},
        "provider_options": {"fixtures": "fx.json"},
    }), "candidate")
    scorers = build_scorers(load_scorer_config(_write(tmp_path / "scorers.json", {
        "scorers": [{"type": "keyword_quality"}],
    })))

    result = run_config(dataset, config, scorers, no_pricing())

    assert result.n_items == 3
    assert result.n_ok == 1
    assert result.n_errors == 2
    by_id = {r.item_id: r for r in result.records}
    for bad_id in ("i1", "i2"):
        assert by_id[bad_id].status == "error"
        assert by_id[bad_id].error
        assert bad_id in by_id[bad_id].error
        assert "m" in by_id[bad_id].error
        assert "non-string" in by_id[bad_id].error
    assert by_id["i3"].status == "ok"
    assert result.aggregates["errors.error_rate"]["value"] == 2 / 3
