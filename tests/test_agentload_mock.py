import asyncio

import aiohttp
import numpy as np

from agentload.mock_server import MockConfig, MockEngine, MockServer, common_prefix_len, to_units


def test_units_and_common_prefix():
    assert to_units([5, 6, 7]).tolist() == [5, 6, 7]
    assert to_units("a b a").tolist()[0] == to_units("a b a").tolist()[2]
    assert to_units([[1, 2]]).tolist() == [1, 2]
    assert common_prefix_len(np.array([1, 2, 3]), np.array([1, 2, 9, 9])) == 2
    assert common_prefix_len(np.array([]), np.array([1])) == 0


def test_lru_eviction_by_session_and_hit_length():
    async def go():
        eng = MockEngine(MockConfig(kv_capacity_tokens=250, key_prefix_len=4))
        a, b, c = (np.arange(100) + 1000 * i for i in (1, 2, 3))
        out = np.arange(10) + 7
        assert eng.lookup(a) == 0
        eng.store(a, out)                                  # a: 110 tokens
        eng.store(b, out)                                  # b: 110 -> 220 total
        assert eng.lookup(a) == 99                         # capped at len-1; touches a (b is now LRU)
        eng.store(c, out)                                  # 330 > 250 -> evict LRU = b
        assert eng.lookup(b) == 0 and eng.lookup(a) == 99 and eng.lookup(c) == 99
        assert eng.stats["evictions"] == 1
        longer = np.concatenate([a, out, np.arange(5) + 1])    # prefix a+out cached, 5 new tokens
        assert eng.lookup(longer) == 110
        eng.flush()
        assert eng.lookup(a) == 0 and eng.used == 0
    asyncio.run(go())


def test_http_cached_styles_and_endpoints():
    async def go():
        prompt = list(range(5000, 5064))
        for style, path in (("usage", ("usage", "prompt_tokens_details")), ("choice_meta", ("choices", 0, "meta_info"))):
            async with MockServer(MockConfig(cached_style=style, fixed_s=0, per_uncached_token_s=0,
                                             per_completion_token_s=0)) as srv:
                async with aiohttp.ClientSession() as http:
                    body = {"model": "m", "prompt": prompt, "max_tokens": 4, "ignore_eos": True}
                    r1 = await (await http.post(srv.url + "/v1/completions", json=body)).json()
                    r2 = await (await http.post(srv.url + "/v1/completions", json=body)).json()
                    for r, want in ((r1, 0), (r2, 63)):
                        node = r
                        for k in path:
                            node = node[k]
                        assert node["cached_tokens"] == want
                    assert r1["usage"]["completion_tokens"] == 4 and r1["usage"]["prompt_tokens"] == 64
                    assert (await http.get(srv.url + "/health")).status == 200
                    assert (await http.get(srv.url + "/v1/models")).status == 200
                    st = await (await http.get(srv.url + "/stats")).json()
                    assert st["cached_tokens"] == 63 and st["prompt_tokens"] == 128
                    assert (await http.post(srv.url + "/flush_cache")).status == 200
                    r3 = await (await http.post(srv.url + "/v1/completions", json=body)).json()
                    assert (r3["usage"].get("prompt_tokens_details") or r3["choices"][0].get("meta_info"))
        async with MockServer(MockConfig(cached_style="none")) as srv:
            async with aiohttp.ClientSession() as http:
                r = await (await http.post(srv.url + "/v1/completions", json={"prompt": prompt, "max_tokens": 2})).json()
                assert "prompt_tokens_details" not in r["usage"] and "meta_info" not in r["choices"][0]
    asyncio.run(go())


def test_http_text_prompt_and_token_ids_and_failure_injection():
    async def go():
        async with MockServer(MockConfig(fail_every_n=3, fixed_s=0, per_uncached_token_s=0,
                                         per_completion_token_s=0)) as srv:
            async with aiohttp.ClientSession() as http:
                url = srv.url + "/v1/completions"
                r = await (await http.post(url, json={"prompt": " the cat sat", "max_tokens": 3})).json()
                assert len(r["choices"][0]["text"].split()) == 3
                r = await (await http.post(url, json={"prompt": [1, 2, 3], "max_tokens": 5,
                                                      "return_token_ids": True})).json()
                assert len(r["choices"][0]["token_ids"]) == 5
                resp = await http.post(url, json={"prompt": [1], "max_tokens": 1})
                assert resp.status == 500                             # every 3rd request fails
    asyncio.run(go())


def test_metrics_styles():
    async def go():
        for style, waiting in (("vllm", "vllm:num_requests_waiting"), ("sglang", "sglang:num_queue_reqs")):
            async with MockServer(MockConfig(metrics_style=style)) as srv:
                async with aiohttp.ClientSession() as http:
                    text = await (await http.get(srv.url + "/metrics")).text()
                    assert waiting in text
                    if style == "vllm":
                        assert "_bucket" in text and "python_gc" in text
    asyncio.run(go())
