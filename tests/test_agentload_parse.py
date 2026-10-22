import json
import math

from agentload.parse import (extract_cached_tokens, extract_output_ids, extract_output_text, extract_usage, get_path,
                             parse_prometheus)


def test_cached_tokens_vllm_usage():
    d = {"usage": {"prompt_tokens": 100, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 64}}}
    assert extract_cached_tokens(d) == (64, "usage.prompt_tokens_details")
    u = extract_usage(d)
    assert (u["prompt_tokens"], u["completion_tokens"], u["cached_tokens"]) == (100, 5, 64)
    assert json.loads(u["raw_usage_json"])["usage"]["prompt_tokens_details"]["cached_tokens"] == 64


def test_cached_tokens_sglang_variants():
    assert extract_cached_tokens({"choices": [{"meta_info": {"cached_tokens": 12}}]}) == (12, "choices.0.meta_info")
    assert extract_cached_tokens({"meta_info": {"cached_tokens": 7}}) == (7, "meta_info")
    assert extract_cached_tokens({"usage": {"cached_tokens": 3}}) == (3, "usage")
    # usage details win over meta_info when both are present
    both = {"usage": {"prompt_tokens_details": {"cached_tokens": 1}}, "choices": [{"meta_info": {"cached_tokens": 2}}]}
    assert extract_cached_tokens(both) == (1, "usage.prompt_tokens_details")


def test_cached_tokens_absent_vs_zero():
    assert extract_cached_tokens({"usage": {"prompt_tokens": 5}}) == (None, "none")
    assert extract_cached_tokens({"usage": {"prompt_tokens_details": None}}) == (None, "none")
    assert extract_cached_tokens({"usage": {"prompt_tokens_details": {"cached_tokens": None}}}) == (None, "none")
    assert extract_cached_tokens({"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}) == (0, "usage.prompt_tokens_details")
    assert extract_cached_tokens({}) == (None, "none")


def test_raw_usage_keeps_scalar_meta_info_only():
    d = {"usage": {"prompt_tokens": 1}, "choices": [{"meta_info": {"cached_tokens": 1, "output_ids": [1, 2, 3],
                                                                   "e2e_latency": 0.5}}]}
    raw = json.loads(extract_usage(d)["raw_usage_json"])
    assert raw["choices.0.meta_info"] == {"cached_tokens": 1, "e2e_latency": 0.5}


def test_output_extraction():
    d = {"choices": [{"text": " hi", "token_ids": [5, 6], "meta_info": {"output_ids": [9]}}]}
    assert extract_output_text(d) == " hi"
    assert extract_output_ids(d, ["choices.0.token_ids"]) == [5, 6]
    assert extract_output_ids(d, ["choices.0.nope", "choices.0.meta_info.output_ids"]) == [9]
    assert extract_output_ids({"choices": [{"token_ids": []}]}, ["choices.0.token_ids"]) is None
    assert extract_output_ids({"choices": [{"token_ids": ["a"]}]}, ["choices.0.token_ids"]) is None
    assert get_path({"a": [{"b": 1}]}, "a.0.b") == 1 and get_path({"a": []}, "a.0.b") is None


PROM = '''# HELP vllm:num_requests_waiting Waiting
# TYPE vllm:num_requests_waiting gauge
vllm:num_requests_waiting{model_name="m, x",engine="0"} 3.0
vllm:num_requests_running{model_name="a \\"q\\" b"} 12
vllm:e2e_request_latency_seconds_bucket{le="0.5",model_name="m"} 4.0
vllm:e2e_request_latency_seconds_count{model_name="m"} 9.0
sglang:cache_hit_rate 0.5
sglang:token_usage{x="}"} NaN
sglang:inf +Inf
python_gc_objects_collected_total{generation="0"} 17.0
garbage line without value
sglang:with_ts 1.5 1700000000000
'''


def test_prometheus_parse_labels_values_and_filters():
    rows = parse_prometheus(PROM, ["vllm:", "sglang:"], ["_bucket"])
    names = [r[0] for r in rows]
    assert "python_gc_objects_collected_total" not in names           # prefix filter
    assert "vllm:e2e_request_latency_seconds_bucket" not in names     # suffix drop
    d = {(n, l): v for n, l, v in rows}
    assert d[("vllm:num_requests_waiting", '{model_name="m, x",engine="0"}')] == 3.0
    assert d[("vllm:num_requests_running", '{model_name="a \\"q\\" b"}')] == 12.0
    assert d[("sglang:cache_hit_rate", "")] == 0.5
    assert math.isnan(d[("sglang:token_usage", '{x="}"}')])
    assert d[("sglang:inf", "")] == math.inf
    assert d[("sglang:with_ts", "")] == 1.5
    allrows = parse_prometheus(PROM)                                    # no filters: everything parsable
    assert "python_gc_objects_collected_total" in [r[0] for r in allrows]
    assert parse_prometheus("") == []
