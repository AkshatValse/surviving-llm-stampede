"""Stand-in for `vllm serve` in tests/test_vllm_scripts.py: the repo's mock server (vLLM-style metrics, usage.prompt_tokens_details)
plus the one route the vLLM job needs that the mock lacks, POST /reset_prefix_cache, answered like vLLM v0.32.0: HTTP 200 with
{"success": true} when no request holds blocks and {"success": false} otherwise (always false when FAKE_VLLM_RESET=fail). Exits by itself after --lifetime seconds so a test
that dies cannot leave a server behind. Usage: python helpers_vllm_server.py serve MODEL --port N [other vllm flags are ignored]."""
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aiohttp import web  # noqa: E402

from agentload.mock_server import ENGINE_KEY, MockConfig, _make_app  # noqa: E402


def main(argv):
    port = int(argv[argv.index("--port") + 1])
    model = argv[argv.index("serve") + 1] if "serve" in argv else "Qwen/Qwen2.5-7B-Instruct"
    app = _make_app(MockConfig(port=port, model_name=model, kv_capacity_tokens=20000))

    async def reset_prefix_cache(request):
        eng = app[ENGINE_KEY]
        if os.environ.get("FAKE_VLLM_RESET") == "fail" or eng.running or eng.waiting:
            return web.json_response({"success": False})
        eng.flush()
        return web.json_response({"success": True})

    app.router.add_post("/reset_prefix_cache", reset_prefix_cache)
    lifetime = float(os.environ.get("FAKE_VLLM_LIFETIME_S", "180"))
    threading.Timer(lifetime, os._exit, [0]).start()
    web.run_app(app, host="127.0.0.1", port=port, print=None, access_log=None)


if __name__ == "__main__":
    main(sys.argv[1:])
