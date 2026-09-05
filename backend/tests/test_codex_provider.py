"""No network or real account is used by these protocol tests."""
import asyncio
from types import SimpleNamespace

import pytest

from app.services.llm import codex


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.events = asyncio.Queue()
        self.account = {"type": "chatgpt", "planType": "plus", "email": "private@example.test"}
        self.closed = False
        self.hang = False
        self.fail = False
        self.on_notification = None

    async def start(self):
        pass

    async def request(self, method, params):
        self.calls.append((method, params))
        if method == "account/read":
            return {"account": self.account}
        if method == "account/login/start":
            return {"type": "chatgptDeviceCode", "loginId": "login1", "verificationUrl": "https://auth.openai.com/codex/device", "userCode": "ABCD"}
        if method == "model/list":
            return {"data": [{"id": "internal-id", "model": "gpt-test", "displayName": "GPT Test"}], "nextCursor": None}
        if method == "thread/start":
            return {"thread": {"id": "thread1"}, "model": "gpt-test"}
        if method == "turn/start":
            if not self.hang:
                self.on_notification("item/completed", {"threadId": "thread1", "turnId": "turn1", "item": {"type": "agentMessage", "id": "item1", "text": '{"answer":42}', "phase": "final_answer"}})
                self.on_notification("thread/tokenUsage/updated", {"threadId": "thread1", "turnId": "turn1", "tokenUsage": {"last": {"inputTokens": 10, "outputTokens": 5, "cachedInputTokens": 3, "totalTokens": 15}}})
                self.on_notification("turn/completed", {"threadId": "thread1", "turn": {"id": "turn1", "status": "failed" if self.fail else "completed", "error": {"message": "SECRET token", "codexErrorInfo": "usageLimitExceeded"} if self.fail else None}})
            return {"turn": {"id": "turn1"}}
        return {}

    async def close(self):
        self.closed = True


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings = SimpleNamespace(codex_cli_path="codex", codex_home=str(tmp_path), codex_timeout_seconds=0.2, codex_model="")
    monkeypatch.setattr(codex, "get_settings", lambda: settings)
    transport = FakeTransport()
    service = codex.CodexService(transport=transport)
    return service, transport


@pytest.mark.asyncio
async def test_chatgpt_status_and_device_login_redact_account(service):
    svc, transport = service
    assert await svc.status() == {"available": True, "connected": True, "plan_type": "plus", "login_pending": False, "error": None}
    login = await svc.start_login()
    assert login == {"login_id": "login1", "verification_url": "https://auth.openai.com/codex/device", "user_code": "ABCD"}
    assert (await svc.status())["login_pending"]
    transport.on_notification("account/login/completed", {"loginId": "login1", "success": False, "error": "secret token"})
    status = await svc.status()
    assert not status["login_pending"]
    assert "secret" not in str(status)
    assert status["error"]


@pytest.mark.asyncio
async def test_no_api_key_billing_fallback(service):
    svc, transport = service
    transport.account = {"type": "apiKey"}
    assert not (await svc.status())["connected"]
    with pytest.raises(codex.CodexError, match="ChatGPT"):
        await svc.generate([{"role": "user", "content": "hello"}])
    assert not any(method == "thread/start" for method, _ in transport.calls)


@pytest.mark.asyncio
async def test_generation_preserves_roles_schema_usage_and_no_tools(service):
    svc, transport = service
    messages = [{"role": "system", "content": [{"type": "text", "text": "System", "cache_control": {"type": "ephemeral"}}]}, {"role": "user", "content": "Question"}, {"role": "assistant", "content": "Earlier answer"}, {"role": "user", "content": "Followup"}]
    schema = {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"], "additionalProperties": False}
    result = await svc.generate(messages, response_format={"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}})
    assert result.content == '{"answer":42}'
    assert result.model == "gpt-test"
    assert result.usage["prompt_tokens"] == 10
    assert result.usage["completion_tokens"] == 5
    assert result.finish_reason == "stop"
    thread = next(p for m, p in transport.calls if m == "thread/start")
    assert thread["ephemeral"] is True
    assert thread["environments"] == []
    assert thread["selectedCapabilityRoots"] == []
    assert thread["baseInstructions"].endswith("System")
    turn = next(p for m, p in transport.calls if m == "turn/start")
    assert turn["outputSchema"] == schema
    assert "Earlier answer" in turn["input"][0]["text"]
    assert "assistant" in turn["input"][0]["text"]
    assert any(m == "thread/unsubscribe" for m, _ in transport.calls)


@pytest.mark.asyncio
async def test_json_object_is_prompt_instruction_not_invalid_schema(service):
    svc, transport = service
    await svc.generate([{"role": "user", "content": "hello"}], response_format={"type": "json_object"})
    thread = next(p for m, p in transport.calls if m == "thread/start")
    turn = next(p for m, p in transport.calls if m == "turn/start")
    assert "JSON object" in thread["baseInstructions"]
    assert "outputSchema" not in turn


@pytest.mark.asyncio
async def test_deadline_interrupts_turn_and_reaps_process(service):
    svc, transport = service
    transport.hang = True
    with pytest.raises(codex.CodexError, match="timed out"):
        await svc.generate([{"role": "user", "content": "hello"}])
    assert transport.closed


@pytest.mark.asyncio
async def test_cancellation_reaps_process(service):
    svc, transport = service
    transport.hang = True
    task = asyncio.create_task(svc.generate([{"role": "user", "content": "hello"}]))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.closed


@pytest.mark.asyncio
async def test_safe_quota_error(service):
    svc, transport = service
    transport.fail = True
    with pytest.raises(codex.CodexError, match="usage limit") as err:
        await svc.generate([{"role": "user", "content": "hello"}])
    assert "SECRET" not in str(err.value)


@pytest.mark.asyncio
async def test_models_cancel_and_logout(service):
    svc, transport = service
    assert await svc.models() == [{"id": "gpt-test", "name": "GPT Test"}]
    await svc.start_login()
    await svc.cancel_login()
    assert ("account/login/cancel", {"loginId": "login1"}) in transport.calls
    assert not (await svc.status())["login_pending"]
    await svc.logout()
    assert any(m == "account/logout" for m, _ in transport.calls)
    await svc.close()
    assert transport.closed


def test_process_environment_does_not_inherit_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://attacker.test")
    monkeypatch.setenv("CODEX_HOME", "/private/account")
    monkeypatch.setenv("AWS_PROFILE", "paid")
    env = codex._subprocess_environment(tmp_path)
    assert env["CODEX_HOME"] == str(tmp_path)
    assert not any(key in env for key in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "AWS_PROFILE"])


@pytest.mark.asyncio
async def test_cancelling_queued_request_does_not_kill_active_generation(service):
    svc, transport = service
    transport.hang = True
    active = asyncio.create_task(svc.generate([{"role": "user", "content": "first"}]))
    await asyncio.sleep(0.01)
    queued = asyncio.create_task(svc.generate([{"role": "user", "content": "second"}]))
    await asyncio.sleep(0.01)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert not transport.closed
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active


@pytest.mark.asyncio
async def test_provider_outer_cancellation_reaps_generation(service, monkeypatch):
    svc, transport = service
    transport.hang = True
    monkeypatch.setattr(codex, "get_codex_service", lambda: svc)
    from app.services import cancellation
    cancellation.register("codex-test")
    try:
        task = asyncio.create_task(codex.CodexProvider().generate("hello", briefing_id="codex-test"))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.closed
    finally:
        cancellation.unregister("codex-test")


@pytest.mark.asyncio
async def test_stdio_handshake_demultiplexing_and_rejection(tmp_path, monkeypatch):
    """Exercise actual process, pipes, requests and shutdown without real Codex."""
    script = tmp_path / "fake-codex"
    script.write_text('#!/usr/bin/env python3\n' + '''import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m.get("method") == "initialize":
        assert m["params"]["capabilities"]["experimentalApi"]
        print(json.dumps({"id": m["id"], "result": {"userAgent": "augustus/0.146.0"}}), flush=True)
    elif m.get("method") == "account/read":
        print(json.dumps({"method": "item/commandExecution/requestApproval", "id": "server1", "params": {}}), flush=True)
        denial = json.loads(sys.stdin.readline())
        assert "error" in denial
        print(json.dumps({"id": m["id"], "result": {"account": None}}), flush=True)
''')
    script.chmod(0o700)
    settings = SimpleNamespace(codex_cli_path=str(script), codex_home=str(tmp_path / "private"), codex_timeout_seconds=1, codex_model="")
    monkeypatch.setattr(codex, "get_settings", lambda: settings)
    svc = codex.CodexService()
    assert (await svc.status())["available"]
    process = svc._transport._process
    await svc.close()
    assert process.returncode is not None


@pytest.mark.asyncio
async def test_unavailable_cli_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(codex, "get_settings", lambda: SimpleNamespace(codex_cli_path="/missing/SECRET/codex", codex_home=str(tmp_path), codex_timeout_seconds=1))
    status = await codex.CodexService().status()
    assert not status["available"]
    assert "SECRET" not in str(status)


def test_reject_cli_without_no_environment_protocol():
    with pytest.raises(codex.CodexError, match="0.146.0"):
        codex._check_version({"userAgent": "augustus/0.145.0"})
    with pytest.raises(codex.CodexError, match="0.146.0"):
        codex._check_version({})
    codex._check_version({"userAgent": "augustus/0.146.0 (Mac OS)"})


@pytest.mark.asyncio
async def test_login_completion_before_start_response_does_not_stay_pending(service):
    svc, transport = service
    original = transport.request
    async def request(method, params):
        result = await original(method, params)
        if method == "account/login/start":
            transport.on_notification("account/login/completed", {"loginId": "login1", "success": False, "error": "SECRET"})
        return result
    transport.request = request
    await svc.start_login()
    status = await svc.status()
    assert not status["login_pending"]
    assert status["error"]
    assert "SECRET" not in str(status)


@pytest.mark.asyncio
async def test_stdio_eof_fails_pending_request_and_process_is_reaped(tmp_path, monkeypatch):
    script = tmp_path / "fake-codex"
    script.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdin.readline()\n')
    script.chmod(0o700)
    monkeypatch.setattr(codex, "get_settings", lambda: SimpleNamespace(codex_cli_path=str(script), codex_home=str(tmp_path / "private"), codex_timeout_seconds=1))
    svc = codex.CodexService()
    status = await svc.status()
    assert not status["available"]
    assert "disconnected" in status["error"]
    assert svc._transport._process is None
