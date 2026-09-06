"""Scripted custom Strands provider. This is a test fixture, NOT a live LLM.

It consumes real tool results but supplies deterministic next steps. Adversarial
scripts exercise the same SDK loop in tests without ever constructing a network
provider. It contains no credential lookup or network client.
"""
import asyncio
import json
from uuid import uuid4

from strands.models import Model

from migration_proof.core.artifacts import SAFE_PATCH, canonical
from .contracts import MODEL_ID


class OfflineModel(Model):
    def __init__(self, context, responses=None, delay_seconds=0):
        self.context = dict(context)
        self.responses = iter(responses) if responses is not None else None
        self.delay_seconds = delay_seconds
        self.last_tool = None
        self.patched = False

    def get_config(self):
        return {"model_id": MODEL_ID, "context_window_limit": 1000000}

    def update_config(self, **model_config):
        if model_config:
            raise ValueError("offline provider configuration is fixed")

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError("use the bounded final explanation")
        yield  # satisfy the custom-provider async generator contract

    def _next(self, messages):
        context = self.context
        if self.responses is not None:
            return next(self.responses)
        if self.last_tool is None:
            return {"name": "inspect_candidate", "input": {"run_id": context["run_id"], "version": context["version"]}}
        content = messages[-1]["content"]
        tool_result = next(item["toolResult"] for item in content if "toolResult" in item)
        result = tool_result["content"][0].get("json")
        if result is None:
            result = json.loads(tool_result["content"][0]["text"])
        value = result["result"]
        if self.last_tool == "inspect_candidate":
            context["digest"] = value["candidate_digest"]
            context["original_digest"] = value["original_digest"]
            return {"name": "run_baseline_tests", "input": {"run_id": context["run_id"], "digest": context["digest"]}}
        if self.last_tool == "run_baseline_tests":
            if value["exit_status"] != 0:
                return {"recommendation": "blocked", "reason_codes": ["regression_test_added", "tenant_boundary_failed", "human_correction_required"]}
            return {"name": "compare_tenant_boundary", "input": {"run_id": context["run_id"], "original_digest": context["original_digest"], "candidate_digest": context["digest"]}}
        if self.last_tool == "compare_tenant_boundary":
            if value["passed"]:
                return {"recommendation": "ready_for_approval", "reason_codes": ["all_gates_passed"]}
            if context.get("has_patch") or self.patched:
                return {"recommendation": "blocked", "reason_codes": ["tenant_boundary_failed", "human_correction_required"]}
            return {"name": "apply_safe_patch", "input": {"run_id": context["run_id"], "digest": context["digest"], "patch": SAFE_PATCH}}
        if self.last_tool == "apply_safe_patch":
            self.patched = True
            context["digest"] = value["candidate_digest"]
            return {"name": "inspect_candidate", "input": {"run_id": context["run_id"], "version": context["version"]}}
        raise ValueError("unknown scripted state")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        response = self._next(messages)
        yield {"messageStart": {"role": "assistant"}}
        if "name" in response:
            self.last_tool = response["name"]
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {"toolUse": {"name": response["name"], "toolUseId": uuid4().hex}}}}
            yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"toolUse": {"input": json.dumps(response["input"])}}}}
            stop_reason = "tool_use"
        else:
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
            yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": json.dumps(response)}}}
            stop_reason = "end_turn"
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": stop_reason}}
        # Synthetic accounting only: these are fixture estimates, not billable usage.
        inputs, outputs = len(canonical(messages)), len(canonical(response))
        yield {"metadata": {"usage": {"inputTokens": inputs, "outputTokens": outputs, "totalTokens": inputs + outputs},
                            "metrics": {"latencyMs": 0}}}
