from __future__ import annotations
import os
import json
from collections import namedtuple
from typing import Any

from google import genai
from google.genai import types as genai_types
from anthropic import Anthropic

from strategies import Strategy
from agent_memory import RunMemory


ToolCall = namedtuple("ToolCall", ["name", "params"])


class GeminiFlashLiteClient:
    model_name = "gemini-2.5-flash"

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)
        self.input_chars = 0
        self.output_chars = 0
        # Per-call telemetry — seconds spent on each LLM call
        self.call_latencies: list[float] = []
        self.api_errors: int = 0
        self.nudge_retries: int = 0

    def call(self, system_prompt: str, user_message: str, tools: list[dict],
             conversation_history: list[dict]) -> ToolCall:
        tool_names = [t["name"] for t in tools]

        # Convert neutral history (role: assistant/user, content: str) to Gemini format
        contents = []
        for msg in conversation_history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})
        self.input_chars += len(system_prompt) + len(user_message)

        # Build function declarations
        declarations = [
            genai_types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=t.get("parameters", {}),
            )
            for t in tools
        ]
        gemini_tools = [genai_types.Tool(function_declarations=declarations)]

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,
            tool_config=genai_types.ToolConfig(
                function_calling_config=genai_types.FunctionCallingConfig(mode="ANY")
            ),
        )

        import time as _time
        text_attempts = 0
        _t0 = _time.perf_counter()
        while True:
            try:
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                # Fail fast on API errors — no retries, no wait
                err_str = str(e)
                print(f"[gemini] api error (fail-fast): {err_str[:120]}")
                self.api_errors += 1
                self.call_latencies.append(_time.perf_counter() - _t0)
                return ToolCall("_api_error", {"reasoning": f"api_error: {err_str[:80]}"})

            tc = self._extract_tool_call(resp)
            if tc is not None:
                self.output_chars += len(tc.name) + len(json.dumps(tc.params))
                self.call_latencies.append(_time.perf_counter() - _t0)
                return tc

            # Model returned text instead of a tool call — nudge it (max 3 nudges)
            text_attempts += 1
            text = self._extract_text(resp) or ""
            self.output_chars += len(text)
            if text_attempts >= 3:
                break
            self.nudge_retries += 1
            contents.append({"role": "model", "parts": [{"text": text or "(no response)"}]})
            contents.append({
                "role": "user",
                "parts": [{
                    "text": (
                        f"You must respond with a tool call. "
                        f"Available tools: {tool_names}. Do not explain, just call a tool."
                    ),
                }],
            })

        # Text-response fallback — still a real decision attempt, just log with marker
        self.call_latencies.append(_time.perf_counter() - _t0)
        return self._fallback(tool_names)

    @staticmethod
    def _extract_tool_call(resp: Any) -> ToolCall | None:
        try:
            for part in resp.candidates[0].content.parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    raw = fc.args or {}
                    # Serialize via JSON to convert MapComposite → plain dict
                    params = json.loads(
                        json.dumps(raw, default=lambda o: list(o) if hasattr(o, "__iter__") else str(o))
                    )
                    return ToolCall(name=fc.name, params=params)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_text(resp: Any) -> str:
        try:
            return resp.text or ""
        except Exception:
            return ""

    @staticmethod
    def _fallback(tool_names: list[str]) -> ToolCall:
        if "play_hand" in tool_names:
            return ToolCall("play_hand", {"cards": [0, 1, 2, 3, 4],
                                          "reasoning": "fallback: LLM failed to produce a tool call"})
        if "finish_shop" in tool_names:
            return ToolCall("finish_shop", {"reasoning": "fallback: LLM failed to produce a tool call"})
        if "select_blind" in tool_names:
            return ToolCall("select_blind", {"reasoning": "fallback: LLM failed to produce a tool call"})
        if "skip_pack" in tool_names:
            return ToolCall("skip_pack", {"reasoning": "fallback: LLM failed to produce a tool call"})
        return ToolCall(tool_names[0], {"reasoning": "fallback"})


class OllamaLocalClient:
    """Ollama local model via OpenAI-compatible API."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 model: str = "qwen3-8b-q4-local",
                 think: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.think = think
        self.input_chars = 0
        self.output_chars = 0
        # Per-call telemetry
        self.call_latencies: list[float] = []
        self.api_errors: int = 0
        self.nudge_retries: int = 0
        # Qwen3 thinking prefix — appended to system prompt to disable slow chain-of-thought
        self._no_think = "/no_think"

    def call(self, system_prompt: str, user_message: str, tools: list[dict],
             conversation_history: list[dict]) -> ToolCall:
        import requests as _req
        import time as _time

        tool_names = [t["name"] for t in tools]

        # Ollama native tool format
        native_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {}),
                },
            }
            for t in tools
        ]

        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        self.input_chars += len(system_prompt) + len(user_message)

        text_attempts = 0
        _t0 = _time.perf_counter()
        while text_attempts < 3:
            try:
                _ts = _time.time()
                print(f"  [ollama] waiting... (think={self.think})", end="\r", flush=True)
                resp = _req.post(
                    f"{self.base_url}/api/chat",   # native endpoint — supports think:false
                    json={
                        "model": self.model,
                        "think": self.think,
                        "tools": native_tools,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=900,                # 15 min — let it think
                )
                resp.raise_for_status()
                data = resp.json()
                _elapsed = _time.time() - _ts
                print(f"  [ollama] {_elapsed:.1f}s", end="\r", flush=True)
            except Exception as e:
                # Fail fast — no retries, no wait
                print(f"[ollama] api error (fail-fast): {e}")
                self.api_errors += 1
                self.call_latencies.append(_time.perf_counter() - _t0)
                return ToolCall("_api_error", {"reasoning": f"api_error: {str(e)[:80]}"})

            msg_data = data.get("message", {})
            tool_calls = msg_data.get("tool_calls") or []
            if tool_calls:
                fc = tool_calls[0].get("function", {})
                name = fc.get("name", "")
                # Native API returns arguments as a dict, not a JSON string
                raw_args = fc.get("arguments", {})
                params = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
                if "reasoning" not in params:
                    params["reasoning"] = "(no reasoning provided)"
                self.output_chars += len(name) + len(str(params))
                reasoning_str = str(params.get('reasoning', '') or '')
                print(f"  → {name}: {reasoning_str[:80]}")
                self.call_latencies.append(_time.perf_counter() - _t0)
                return ToolCall(name=name, params=params)

            # Model returned text instead of tool call — nudge it
            text_attempts += 1
            self.nudge_retries += 1
            text = msg_data.get("content") or ""
            self.output_chars += len(text)
            messages.append({"role": "assistant", "content": text or "(no response)"})
            messages.append({
                "role": "user",
                "content": f"You must call one of these tools: {tool_names}. Do not explain.",
            })

        self.call_latencies.append(_time.perf_counter() - _t0)
        return self._fallback(tool_names)

    @staticmethod
    def _fallback(tool_names: list[str]) -> ToolCall:
        if "play_hand" in tool_names:
            return ToolCall("play_hand", {"cards": [0, 1, 2, 3, 4],
                                          "reasoning": "fallback: LLM failed to produce a tool call"})
        if "finish_shop" in tool_names:
            return ToolCall("finish_shop", {"reasoning": "fallback: LLM failed to produce a tool call"})
        if "select_blind" in tool_names:
            return ToolCall("select_blind", {"reasoning": "fallback: LLM failed to produce a tool call"})
        if "skip_pack" in tool_names:
            return ToolCall("skip_pack", {"reasoning": "fallback: LLM failed to produce a tool call"})
        return ToolCall(tool_names[0], {"reasoning": "fallback"})


REPORT_SYSTEM_PROMPT = """You are a senior Balatro strategist writing a post-run analysis.

You will receive a JSON dump of a complete run: strategy config, full action log
(every decision with the agent's own reasoning), wallet/hand/blind/joker history,
and final outcome.

Produce a clear, structured markdown report with these exact sections:

## Run Summary
strategy, deck, stake, seed, outcome, final ante

## Economy Analysis
Wallet trajectory per ante, interest efficiency, spend vs reserve balance,
best/worst economy decisions.

## Combo Performance
Hands played breakdown by type, discard efficiency, hand level progression,
rounds per blind average.

## Joker Decisions
Every buy/sell decision with cost and context, joker synergy assessment
(did purchased jokers fire together?), missed opportunities.

## Blind Strategy
Skips taken vs available, tag rewards received, boss blind outcomes.

## Key Decision Points
Top 3 decisions that most impacted the run (positive or negative) with the
agent's own reasoning quoted from action_log.

## Recommendations
Concrete changes to strategy parameters that would improve this run.
"""


class OpenAIGameClient:
    """OpenAI client for game decisions (tool use)."""
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        from openai import OpenAI
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.input_chars = 0
        self.output_chars = 0
        self.call_latencies: list[float] = []
        self.api_errors: int = 0
        self.nudge_retries: int = 0

    @staticmethod
    def _to_openai_tools(tools: list[dict]) -> list[dict]:
        """Convert our schema dicts to OpenAI tool format."""
        return [{"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("parameters", {"type": "object", "properties": {}}),
        }} for t in tools]

    def call(self, system_prompt: str, user_message: str, tools: list[dict],
             conversation_history: list[dict]) -> ToolCall:
        import time as _time
        tool_names = [t["name"] for t in tools]
        openai_tools = self._to_openai_tools(tools)

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        for m in conversation_history:
            role = "assistant" if m.get("role") in ("model", "assistant") else "user"
            messages.append({"role": role, "content": str(m.get("content", ""))})
        messages.append({"role": "user", "content": user_message})

        self.input_chars += sum(len(str(m["content"])) for m in messages)

        # gpt-5-mini / o-series use max_completion_tokens; older models use max_tokens
        _new_token_api = any(self.model.startswith(p) for p in ("o1", "o3", "o4", "gpt-5"))
        _token_kwargs = {"max_completion_tokens": 512} if _new_token_api else {"max_tokens": 512}

        _t0 = _time.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools,
                tool_choice="required",   # always call a tool
                **_token_kwargs,
            )
        except Exception as e:
            self.api_errors += 1
            self.call_latencies.append(_time.perf_counter() - _t0)
            err = str(e)[:80]
            print(f"  [openai] api error (fail-fast): {err}")
            return ToolCall("_api_error", {"reasoning": f"api_error: {err}"})

        self.call_latencies.append(_time.perf_counter() - _t0)

        msg = resp.choices[0].message
        finish_reason = resp.choices[0].finish_reason
        if finish_reason not in ("tool_calls", "stop", None):
            print(f"  [openai] unexpected finish_reason={finish_reason!r}")
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            try:
                params = json.loads(tc.function.arguments)
            except Exception:
                params = {}
            reasoning = params.get("reasoning", "")
            print(f"  → {tc.function.name}: {reasoning[:80]}")
            self.output_chars += len(tc.function.arguments)
            return ToolCall(name=tc.function.name, params=params)

        # No tool call — nudge once then fallback
        text_reply = (msg.content or "").strip()[:120]
        print(f"  [openai] no tool call — model said: {text_reply!r}")
        self.nudge_retries += 1

        # Nudge: append model reply + demand a tool call
        nudge_messages = messages + [
            {"role": "assistant", "content": msg.content or ""},
            {"role": "user", "content":
             f"You MUST respond by calling one of the available tools: "
             f"{', '.join(tool_names)}. Do not write text — call a tool now."},
        ]
        try:
            resp2 = self.client.chat.completions.create(
                model=self.model,
                messages=nudge_messages,
                tools=openai_tools,
                tool_choice="required",
                **_token_kwargs,
            )
            msg2 = resp2.choices[0].message
            if msg2.tool_calls:
                tc = msg2.tool_calls[0]
                try:
                    params = json.loads(tc.function.arguments)
                except Exception:
                    params = {}
                print(f"  [openai] nudge succeeded → {tc.function.name}")
                self.output_chars += len(tc.function.arguments)
                return ToolCall(name=tc.function.name, params=params)
        except Exception as e:
            print(f"  [openai] nudge failed: {str(e)[:60]}")

        print(f"  [openai] fallback after nudge")
        return self._fallback(tool_names)

    @staticmethod
    def _fallback(tool_names: list[str]) -> ToolCall:
        if "play_hand" in tool_names:
            return ToolCall("play_hand", {"cards": [0, 1, 2, 3, 4], "reasoning": "fallback"})
        if "finish_shop" in tool_names:
            return ToolCall("finish_shop", {"reasoning": "fallback"})
        if "select_blind" in tool_names:
            return ToolCall("select_blind", {"reasoning": "fallback"})
        if "skip_pack" in tool_names:
            return ToolCall("skip_pack", {"reasoning": "fallback"})
        return ToolCall(tool_names[0], {"reasoning": "fallback"})


class ClaudeGameClient:
    """Claude client for game decisions (tool use). Supports sonnet and haiku."""
    MODELS = {
        "sonnet": "claude-sonnet-4-5",
        "haiku":  "claude-haiku-4-5",
    }

    def __init__(self, model: str = "haiku", api_key: str | None = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=api_key)
        self.model = self.MODELS.get(model, model)   # allow raw model ID too
        self.input_chars = 0
        self.output_chars = 0
        self.call_latencies: list[float] = []
        self.api_errors: int = 0
        self.nudge_retries: int = 0

    @staticmethod
    def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
        """Convert our schema dicts to Anthropic tool format."""
        out = []
        for t in tools:
            out.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def call(self, system_prompt: str, user_message: str, tools: list[dict],
             conversation_history: list[dict]) -> ToolCall:
        import time as _time
        tool_names = [t["name"] for t in tools]
        anthropic_tools = self._to_anthropic_tools(tools)

        # Build messages from history + current user message
        # Normalise history roles: Gemini uses "model", Anthropic uses "assistant"
        history = []
        for m in conversation_history:
            role = "assistant" if m.get("role") == "model" else m.get("role", "user")
            history.append({"role": role, "content": m.get("content", "")})
        messages = history + [{"role": "user", "content": user_message}]

        self.input_chars += len(system_prompt) + sum(
            len(str(m.get("content", ""))) for m in messages)

        _t0 = _time.perf_counter()
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=anthropic_tools,
                tool_choice={"type": "any"},   # force tool use every time
                messages=messages,
            )
        except Exception as e:
            self.api_errors += 1
            self.call_latencies.append(_time.perf_counter() - _t0)
            err = str(e)[:80]
            print(f"  [claude] api error (fail-fast): {err}")
            return ToolCall("_api_error", {"reasoning": f"api_error: {err}"})

        self.call_latencies.append(_time.perf_counter() - _t0)

        # Extract tool use block
        for block in resp.content:
            if block.type == "tool_use":
                params = dict(block.input) if block.input else {}
                reasoning = params.get("reasoning", "")
                print(f"  → {block.name}: {reasoning[:80]}")
                self.output_chars += len(str(block.input))
                return ToolCall(name=block.name, params=params)

        # No tool call returned — fallback
        self.nudge_retries += 1
        print(f"  [claude] no tool call — fallback")
        return self._fallback(tool_names)

    @staticmethod
    def _fallback(tool_names: list[str]) -> ToolCall:
        if "play_hand" in tool_names:
            return ToolCall("play_hand", {"cards": [0, 1, 2, 3, 4],
                            "reasoning": "fallback: no tool call"})
        if "finish_shop" in tool_names:
            return ToolCall("finish_shop", {"reasoning": "fallback: no tool call"})
        if "select_blind" in tool_names:
            return ToolCall("select_blind", {"reasoning": "fallback: no tool call"})
        if "skip_pack" in tool_names:
            return ToolCall("skip_pack", {"reasoning": "fallback: no tool call"})
        return ToolCall(tool_names[0], {"reasoning": "fallback"})


class OpenAIReportClient:
    """OpenAI client for post-run report generation (drop-in for ClaudeSonnetClient)."""
    model_name = "gpt-4.1"   # good balance of quality + cost for report writing

    def __init__(self, api_key: str | None = None):
        from openai import OpenAI
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)
        self.input_chars = 0
        self.output_chars = 0

    def generate_report(self, memory: RunMemory, strategy: Strategy) -> str:
        user_payload = json.dumps({
            "strategy": {
                "name": strategy.name,
                "combo": strategy.combo.__dict__,
                "spend": strategy.spend.__dict__,
                "blind": strategy.blind.__dict__,
            },
            "memory": memory.to_json(),
        }, indent=2, default=str)

        self.input_chars += len(REPORT_SYSTEM_PROMPT) + len(user_payload)

        resp = self.client.chat.completions.create(
            model=self.model_name,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user",   "content": user_payload},
            ],
        )
        out = resp.choices[0].message.content or ""
        self.output_chars += len(out)
        return out


class ClaudeSonnetClient:
    model_name = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=api_key)
        self.input_chars = 0
        self.output_chars = 0

    def generate_report(self, memory: RunMemory, strategy: Strategy) -> str:
        user_payload = json.dumps({
            "strategy": {
                "name": strategy.name,
                "combo": strategy.combo.__dict__,
                "spend": strategy.spend.__dict__,
                "blind": strategy.blind.__dict__,
            },
            "memory": memory.to_json(),
        }, indent=2, default=str)

        self.input_chars += len(REPORT_SYSTEM_PROMPT) + len(user_payload)

        resp = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=[{
                "type": "text",
                "text": REPORT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_payload}],
        )
        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        self.output_chars += len(out)
        return out
