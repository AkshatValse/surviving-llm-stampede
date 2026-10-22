"""Open-loop multi-turn agent-session load generator for OpenAI-compatible LLM servers.

Reproduces the workload of the prefix-cache metastability simulator (``prefixmeta``) against a real
engine (SGLang / vLLM) or against the local mock server in :mod:`agentload.mock_server`.
"""
__version__ = "0.1.0"
