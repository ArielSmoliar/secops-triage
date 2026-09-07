"""Narrow text-only OpenAI Chat Completions provider for the pinned Strands SDK."""
import asyncio
import http.client
import json
import re
import ssl

import certifi
from strands.models import Model

from migration_proof.core.artifacts import canonical
from migration_proof.core.contracts import Rejected
from .openai_preflight import MODEL_ID

MAX_REQUEST_BYTES = 262144
MAX_RESPONSE_BYTES = 65536
TOOL_NAMES = {"inspect_candidate", "run_baseline_tests", "compare_tenant_boundary", "apply_safe_patch"}


def validate_key(key):
    if type(key) is not str or not 1 <= len(key) <= 512 or not all(33 <= ord(c) <= 126 for c in key):
        raise Rejected("a valid local API key is required")


def _post(body, key):
    """Exactly one HTTPS request. No proxy discovery, redirects, or retries."""
    validate_key(key)
    connection = http.client.HTTPSConnection("api.openai.com", timeout=20,
                                              context=ssl.create_default_context(cafile=certifi.where()))
    try:
        connection.request("POST", "/v1/chat/completions", body=body,
                           headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                    "Accept": "application/json", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Content-Encoding", "identity") != "identity":
            raise Rejected("OpenAI request failed")
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise Rejected("OpenAI response exceeded limit")
        return json.loads(data)
    except Exception:
        raise Rejected("OpenAI transport failed") from None
    finally:
        connection.close()


def payload(messages, tool_specs, system_prompt, output_tokens, *, allowed_tools=None):
    names = TOOL_NAMES if allowed_tools is None else allowed_tools
    if type(system_prompt) is not str or {s["name"] for s in tool_specs or []} != names or len(tool_specs) != 4:
        raise Rejected("fixed text prompt and four tools required")
    converted = [{"role": "system", "content": system_prompt}]
    for message in messages:
        role, blocks = message["role"], message["content"]
        if role not in ("user", "assistant") or not blocks:
            raise Rejected("unsupported message")
        if all(set(b) == {"text"} and type(b["text"]) is str for b in blocks):
            converted.append({"role": role, "content": "\n".join(b["text"] for b in blocks)})
        elif role == "assistant" and len(blocks) == 1 and set(blocks[0]) == {"toolUse"}:
            use = blocks[0]["toolUse"]
            converted.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": use["toolUseId"], "type": "function", "function": {
                    "name": use["name"], "arguments": canonical(use["input"]).decode()}}]})
        elif role == "user" and len(blocks) == 1 and set(blocks[0]) == {"toolResult"}:
            result = blocks[0]["toolResult"]
            if any(set(b) not in ({"text"}, {"json"}) for b in result["content"]):
                raise Rejected("unsupported tool result modality")
            converted.append({"role": "tool", "tool_call_id": result["toolUseId"],
                              "content": canonical(result["content"]).decode()})
        else:
            raise Rejected("unsupported message modality")
    body = canonical({"model": MODEL_ID, "messages": converted, "stream": False, "store": False,
                      "n": 1, "modalities": ["text"], "service_tier": "default",
                      "max_completion_tokens": output_tokens, "temperature": 0,
                      "parallel_tool_calls": False, "tool_choice": "auto",
                      "tools": [{"type": "function", "function": {
                          "name": s["name"], "description": s["description"],
                          "parameters": s["inputSchema"]["json"]}} for s in tool_specs]})
    if len(body) > MAX_REQUEST_BYTES:
        raise Rejected("OpenAI request exceeded limit")
    return body


def parse_response(response):
    if (type(response) is not dict or response.get("model") != MODEL_ID
            or response.get("service_tier") != "default" or len(response.get("choices", [])) != 1):
        raise Rejected("unexpected OpenAI response identity")
    choice = response["choices"][0]
    message = choice["message"]
    if message.get("role") != "assistant" or message.get("refusal") or message.get("audio"):
        raise Rejected("unsupported OpenAI response")
    if choice["finish_reason"] == "tool_calls":
        calls = message.get("tool_calls", [])
        if len(calls) != 1 or message.get("content") not in (None, ""):
            raise Rejected("exactly one tool and no prose required")
        call = calls[0]
        if call["type"] != "function" or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call["id"]):
            raise Rejected("invalid function call")
        use = {"toolUseId": call["id"], "name": call["function"]["name"],
               "input": json.loads(call["function"]["arguments"])}
        return {"toolUse": use}, "tool_use"
    if choice["finish_reason"] == "stop" and not message.get("tool_calls") and type(message.get("content")) is str:
        return {"text": message["content"]}, "end_turn"
    raise Rejected("incomplete OpenAI response")


class OpenAIModel(Model):
    def __init__(self, ledger, session_id, api_key, *, allowed_tools=None):
        self.allowed_tools = TOOL_NAMES if allowed_tools is None else frozenset(allowed_tools)
        validate_key(api_key)
        self.ledger, self.session_id, self._api_key = ledger, session_id, api_key

    def get_config(self):
        return {"model_id": MODEL_ID}

    def update_config(self, **model_config):
        if model_config:
            raise Rejected("OpenAI provider configuration is fixed")

    async def structured_output(self, *args, **kwargs):
        raise Rejected("use the bounded final explanation")
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        # Validate and cap the payload before reserving; the authoritative plan is
        # read again at reservation. No network work occurs without a durable intent.
        body = payload(messages, tool_specs, system_prompt, 1, allowed_tools=self.allowed_tools)
        request_id, plan = self.ledger.reserve(self.session_id)
        try:
            body = payload(messages, tool_specs, system_prompt, plan.max_output_tokens, allowed_tools=self.allowed_tools)
            response = await asyncio.to_thread(_post, body, self._api_key)
            content, stop = parse_response(response)
            if len(canonical(content)) > 16384:
                raise Rejected("model response exceeded acceptance limit")
            self.ledger.settle(self.session_id, request_id, response.get("usage"))
        except asyncio.CancelledError:
            self.ledger.uncertain(self.session_id, request_id)
            raise
        except Exception:
            self.ledger.uncertain(self.session_id, request_id)
            raise Rejected("OpenAI call stopped; reservation retained") from None
        yield {"messageStart": {"role": "assistant"}}
        if "toolUse" in content:
            use = content["toolUse"]
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {"toolUse": {"name": use["name"], "toolUseId": use["toolUseId"]}}}}
            delta = {"toolUse": {"input": canonical(use["input"]).decode()}}
        else:
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
            delta = content
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": delta}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": stop}}
        usage = response["usage"]
        yield {"metadata": {"usage": {"inputTokens": usage["prompt_tokens"],
                                       "outputTokens": usage["completion_tokens"],
                                       "totalTokens": usage["total_tokens"]}, "metrics": {"latencyMs": 0}}}
