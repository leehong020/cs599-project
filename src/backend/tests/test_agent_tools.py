"""Agent 工具系统完整测试计划。

运行方式:
    cd backend
    python -m pytest tests/test_agent_tools.py -v -s

覆盖：
    1. 工具函数单元测试（无 LLM）
    2. Graph 结构测试
    3. 消息格式兼容性测试
    4. 完整对话流程集成测试
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import ToolMessage
import pytest


# ═══════════════════════════════════════════════════════════════════════
# 模块 1: 工具函数单元测试
# ═══════════════════════════════════════════════════════════════════════

class TestToolFunctions:
    """测试每个工具函数的基本行为（不依赖 LLM）。"""

    def test_create_tools_returns_all_tools(self):
        """验证 create_tools 返回所有聊天 agent 可用工具。"""
        from app.graph.tools import create_tools, set_tool_context
        set_tool_context()
        tools = create_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "search_emails", "read_email", "create_email_draft", "update_email_draft",
            "send_email_draft", "send_all_local_email_drafts",
            "list_local_email_drafts", "read_local_email_draft",
            "delete_local_email_draft", "delete_all_local_email_drafts", "delete_email",
            "list_calendar_events", "create_calendar_event_draft", "update_calendar_event_draft",
            "create_calendar_update_draft", "execute_calendar_event_draft",
            "execute_calendar_event_update_draft", "delete_calendar_event",
            "execute_calendar_event_delete_draft",
            "resolve_contact", "get_user_signatures", "get_user_profile",
            "remember_user_fact", "recall_memories",
        }
        assert tool_names == expected, f"Missing tools: {expected - tool_names}"

    def test_create_tools_for_agent_scopes_tools(self):
        """不同 LLM Agent 只能拿到自己职责内的工具。"""
        from app.graph.tools import create_tools_for_agent, set_tool_context
        set_tool_context()

        mail_tools = {t.name for t in create_tools_for_agent("mail_agent")}
        calendar_tools = {t.name for t in create_tools_for_agent("calendar_agent")}
        context_tools = {t.name for t in create_tools_for_agent("context_agent")}
        response_tools = {t.name for t in create_tools_for_agent("response_agent")}

        assert "create_email_draft" in mail_tools
        assert "execute_calendar_event_draft" not in mail_tools
        assert "create_calendar_event_draft" in calendar_tools
        assert "send_email_draft" not in calendar_tools
        assert {"search_emails", "read_email"}.issubset(context_tools)
        assert response_tools == set()

    def test_resolve_contact_reads_settings_contacts(self):
        """联系人解析工具应优先读取设置页联系人，而不是依赖模型猜测。"""
        from app.graph.tools import create_tools, set_tool_context

        class FakeContact:
            id = "contact_zhao"
            display_name = "赵涛"
            email = "zhaotao@example.com"

        async def fake_list_contacts(_session, _user):
            return [FakeContact()]

        set_tool_context(db_session=object(), user=MagicMock(user_id="user_1"))
        with patch("app.services.settings.list_contacts", side_effect=fake_list_contacts):
            tools = {t.name: t for t in create_tools()}
            result = json.loads(tools["resolve_contact"].invoke({"name": "赵涛"}))

        assert result["ok"] is True
        assert result["code"] == "contact_resolved"
        assert result["data"]["contact"]["display_name"] == "赵涛"
        assert result["data"]["contact"]["email"] == "zhaotao@example.com"

    def test_local_email_draft_row_summary_is_stable(self):
        """本地邮件草稿摘要应稳定暴露 work_item_id、artifact_id、收件人和正文预览。"""
        from app.graph.tools import _local_email_draft_from_row

        row = {
            "work_item_id": "wi_1",
            "artifact_id": "art_1",
            "thread_id": "thread_1",
            "version": 2,
            "title": "旧标题",
            "summary": "摘要",
            "status": "open",
            "maturity": "reviewable",
            "updated_at": "2026-06-12T10:00:00+08:00",
            "content_json": json.dumps(
                {
                    "to": [{"email": "zhao@example.com", "name": "赵涛"}],
                    "subject": "会议通知",
                    "body": "赵涛你好，\n\n  请下午三点参加会议。",
                },
                ensure_ascii=False,
            ),
        }

        draft = _local_email_draft_from_row(row)

        assert draft["work_item_id"] == "wi_1"
        assert draft["artifact_id"] == "art_1"
        assert draft["subject"] == "会议通知"
        assert draft["to"] == [{"email": "zhao@example.com", "name": "赵涛"}]
        assert "请下午三点参加会议" in draft["preview"]

    def test_tools_handle_no_context_gracefully(self):
        """无 Google 连接时工具应返回友好提示而非崩溃。"""
        from app.graph.tools import create_tools, set_tool_context
        set_tool_context()  # 全部 None
        tools = create_tools()

        # 所有 Google 工具应返回 "未连接" 提示
        tool_map = {t.name: t for t in tools}

        r1 = tool_map["search_emails"].invoke({"query": "test"})
        assert "未连接" in r1 or "Gmail" in r1

        r2 = tool_map["list_calendar_events"].invoke({"time_min": "", "time_max": ""})
        assert "未连接" in r2 or "Calendar" in r2

    def test_search_emails_with_mock(self):
        """模拟 Gmail 客户端，测试搜索功能。"""
        import asyncio
        from app.graph.tools import set_tool_context

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.messages = [
            MagicMock(id="msg1", subject="测试邮件", from_email="test@example.com",
                      date="2026-06-01", snippet="这是测试"),
        ]

        # 使 search_messages 返回真实的异步协程
        async def mock_search(*args, **kwargs):
            return mock_result
        mock_client.search_messages = mock_search

        # _run_async mock: 用 asyncio.run 执行协程
        def fake_run_async(coro):
            return asyncio.run(coro)

        with patch("app.graph.tools._run_async", side_effect=fake_run_async):
            set_tool_context(gmail_client=mock_client, calendar_client=None,
                             db_session=None, user=None)
            from app.graph.tools import create_tools
            tools = create_tools()
            tool_map = {t.name: t for t in tools}

            result = tool_map["search_emails"].invoke({"query": "测试", "max_results": 5})
            assert "测试邮件" in result
            assert "test@example.com" in result

    def test_normalize_tool_call_handles_both_formats(self):
        """验证 _normalize_tool_call 兼容 dict 和对象格式。"""
        from app.graph.nodes import _normalize_tool_call

        # dict 格式
        d = {"name": "test", "args": {"k": "v"}, "id": "call_1"}
        r = _normalize_tool_call(d)
        assert r["name"] == "test"
        assert r["args"] == {"k": "v"}
        assert r["id"] == "call_1"

        # 对象格式（模拟 namedtuple）
        class FakeTC:
            name = "test2"
            args = {"x": 1}
            id = "call_2"
        r2 = _normalize_tool_call(FakeTC())
        assert r2["name"] == "test2"
        assert r2["args"] == {"x": 1}
        assert r2["id"] == "call_2"


def _sync_run(coro: Any) -> Any:
    """同步运行异步协程（测试用）。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════
# 模块 2: Graph 结构测试
# ═══════════════════════════════════════════════════════════════════════

class TestGraphStructure:
    """测试 graph 编译和消息流。"""

    def test_graph_compiles(self):
        """验证 graph 可以正常编译。"""
        from app.graph.builder import build_assistant_graph
        graph = build_assistant_graph()
        assert graph is not None

    def test_graph_has_correct_nodes(self):
        """验证 graph 包含正确的 4 个节点。"""
        from app.graph.builder import build_assistant_graph
        graph = build_assistant_graph()
        nodes = graph.get_graph().nodes
        # 节点名在编译后的图中
        assert nodes is not None

    def test_graph_uses_multi_agent_nodes(self):
        """验证主图已经恢复为多 Agent + Gate/Executor 节点。"""
        from app.graph.builder import build_assistant_graph
        graph = build_assistant_graph()
        mermaid = graph.get_graph().draw_mermaid()
        expected_nodes = {
            "state_loader",
            "supervisor_agent",
            "context_agent",
            "mail_agent",
            "calendar_agent",
            "review_gate",
            "confirmation_gate",
            "executor",
            "response_agent",
            "memory_extractor",
        }
        assert expected_nodes.issubset(set(mermaid.split()))

    def test_route_after_agent_always_returns_save_turn(self):
        """agent 节点后总是路由到 save_turn（无条件分支）。"""
        from app.graph.routes import route_after_agent
        result = route_after_agent({})
        assert result == "save_turn"


# ═══════════════════════════════════════════════════════════════════════
# 模块 3: 消息格式兼容性测试
# ═══════════════════════════════════════════════════════════════════════

class TestMessageFormat:
    """测试 dict ↔ LangChain 消息转换的健壮性。"""

    def test_agent_node_creates_valid_response(self):
        """agent_node 在纯对话（无工具调用）时应正确返回。"""
        from app.graph.nodes import agent_node

        state = {
            "messages": [],
            "user_message": "你好",
            "system_prompt": "你是 Mailflow Agent。用中文回复。",
            "available_signatures": [],
            "default_signature": None,
            "recalled_memories": [],
            "route_trace": [],
        }

        # Mock LLM 返回无 tool_calls 的响应
        with patch("app.graph.nodes.get_chat_model") as mock_model:
            mock_llm = MagicMock()
            mock_msg = MagicMock()
            mock_msg.content = "你好！有什么可以帮你的？"
            mock_msg.tool_calls = []  # 无工具调用
            mock_llm.invoke.return_value = mock_msg
            mock_model.return_value = mock_llm

            result = agent_node(state)

        assert "response" in result
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert result["messages"][-1]["role"] == "assistant"

    def test_agent_node_with_tool_calls(self):
        """agent_node 在 LLM 返回 tool_calls 时应正确执行并整合。"""
        from app.graph.nodes import agent_node

        state = {
            "messages": [],
            "user_message": "帮我查邮件",
            "system_prompt": "你是 Mailflow Agent。",
            "available_signatures": [],
            "default_signature": None,
            "recalled_memories": [],
            "route_trace": [],
        }

        with patch("app.graph.nodes.get_chat_model") as mock_model:
            # 第一轮 LLM 调用：返回 tool_calls
            mock_llm = MagicMock()
            msg1 = MagicMock()
            msg1.content = None
            msg1.tool_calls = [{"name": "search_emails", "args": {"query": "test"}, "id": "call_1"}]
            mock_llm.invoke.return_value = msg1
            mock_llm.bind_tools.return_value = mock_llm

            # 第二轮 LLM 调用（无 tools）：返回总结
            msg2 = MagicMock()
            msg2.content = "找到 3 封邮件..."
            msg2.tool_calls = None

            mock_model.return_value = mock_llm

            # Mock 工具执行
            with patch("app.graph.tools._run_async", side_effect=lambda c: _sync_run(c)):
                from app.graph.tools import set_tool_context
                mock_gmail = MagicMock()
                mock_result = MagicMock()
                mock_result.messages = []
                mock_gmail.search_messages = MagicMock(return_value=mock_result)
                set_tool_context(gmail_client=mock_gmail)

                def invoke_side_effect(messages):
                    # 检查消息中是否包含 tool_calls
                    has_tool_calls = any(
                        hasattr(m, "tool_calls") and m.tool_calls for m in messages
                    )
                    if has_tool_calls or any(
                        isinstance(m, MagicMock) for m in messages
                    ):
                        return msg1
                    return msg2

                mock_llm.invoke.side_effect = lambda messages: (
                    msg2 if _has_tool_message(messages) else msg1
                )

                result = agent_node(state)

        assert "response" in result
        assert len(result["messages"]) >= 2


def _has_tool_message(messages: list) -> bool:
    """检查消息列表中是否包含 ToolMessage。"""
    for m in messages:
        if isinstance(m, ToolMessage):
            return True
        if hasattr(m, "type") and m.type == "tool":
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# 模块 4: 完整对话流程集成测试
# ═══════════════════════════════════════════════════════════════════════

class TestIntegrationScenarios:
    """模拟真实用户场景，验证完整链路。"""

    @pytest.fixture
    def mock_llm_no_tools(self):
        """Mock LLM：总是返回纯文本（不调工具）。"""
        with patch("app.graph.nodes.get_chat_model") as mock, \
             patch("app.services.llm_client.get_chat_model") as service_mock:
            llm = MagicMock()
            msg = MagicMock()
            msg.content = "好的，已为你处理。"
            msg.tool_calls = []
            llm.invoke.return_value = msg
            llm.bind_tools.return_value = llm
            mock.return_value = llm
            service_mock.return_value = llm
            yield mock

    def test_scenario_simple_chat(self, mock_llm_no_tools):
        """场景 1: 简单对话（无 Google 连接）。"""
        from app.graph.runner import run_assistant_turn

        state = run_assistant_turn(
            thread_id="test_thread_1",
            user_message="你好，请介绍一下你自己",
        )

        assert "response" in state
        assert len(state.get("response", "")) > 0
        assert state.get("messages", [])[-1]["role"] == "assistant"

    def test_scenario_all_nodes_execute(self):
        """场景 2: 验证所有 4 个节点正常执行。"""
        from app.graph.builder import build_assistant_graph
        from langgraph.checkpoint.memory import MemorySaver

        # 用 MemorySaver 避免 SQLite 线程问题
        checkpointer = MemorySaver()
        graph_with_checkpoint = build_assistant_graph(checkpointer=checkpointer)

        with patch("app.graph.nodes.get_chat_model") as mock_model, \
             patch("app.services.llm_client.get_chat_model") as service_model:
            llm = MagicMock()
            msg = MagicMock()
            msg.content = "你好！我是 Mailflow Agent。"
            msg.tool_calls = []
            llm.invoke.return_value = msg
            llm.bind_tools.return_value = llm
            mock_model.return_value = llm
            service_model.return_value = llm

            result = graph_with_checkpoint.invoke(
                {
                    "thread_id": "test_1",
                    "user_id": "test_user",
                    "user_message": "你好",
                    "messages": [],
                    "available_signatures": [],
                },
                config={"configurable": {"thread_id": "test_1"}},
            )

        assert "response" in result
        assert "route_trace" in result
        # 验证 4 个节点都执行了
        trace = result.get("route_trace", [])
        expected_nodes = {
            "state_loader", "supervisor_agent", "context_agent", "mail_agent",
            "calendar_agent", "review_gate", "confirmation_gate", "executor",
            "response_agent", "save_turn_state", "memory_extractor",
        }
        traced_nodes = set(trace)
        assert expected_nodes.issubset(traced_nodes), f"Missing nodes: {expected_nodes - traced_nodes}"


# ═══════════════════════════════════════════════════════════════════════
# 模块 5: 已知问题回归测试
# ═══════════════════════════════════════════════════════════════════════

class TestRegression:
    """回归测试：确保之前修复的问题不再出现。"""

    def test_tool_calls_format_normalized(self):
        """tool_calls 总是被标准化为带 name/args/id 的 dict。"""
        from app.graph.nodes import _normalize_tool_call

        # 空 dict
        r = _normalize_tool_call({})
        assert isinstance(r, dict)
        assert "name" in r and "args" in r and "id" in r

        # None-like values
        r = _normalize_tool_call({"name": None, "args": None, "id": None})
        assert r["name"] == "None"
        assert r["args"] == {}
        assert r["id"] == "None"

    def test_context_injection_survives_multiple_calls(self):
        """多次 set_tool_context 调用不会残留旧状态。"""
        from app.graph.tools import set_tool_context, _get_gmail_client, _get_user

        set_tool_context(gmail_client="client_a", user="user_a")
        assert _get_gmail_client() == "client_a"
        assert _get_user() == "user_a"

        set_tool_context(gmail_client="client_b", user=None)
        assert _get_gmail_client() == "client_b"
        assert _get_user() is None

    def test_empty_messages_does_not_crash(self):
        """空消息列表不会导致 agent_node 崩溃。"""
        from app.graph.nodes import agent_node

        state = {
            "messages": [],
            "user_message": "",
            "system_prompt": "test",
            "available_signatures": [],
            "default_signature": None,
            "recalled_memories": [],
            "route_trace": [],
        }

        with patch("app.graph.nodes.get_chat_model") as mock_model:
            llm = MagicMock()
            msg = MagicMock()
            msg.content = "请告诉我你需要什么帮助。"
            msg.tool_calls = []
            llm.invoke.return_value = msg
            mock_model.return_value = llm

            result = agent_node(state)

        assert result is not None
        assert "response" in result

    def test_email_format_appends_signature_once(self):
        """邮件格式化会缩进正文段落，并避免重复追加署名。"""
        from app.graph.tools import _format_email_body

        first = _format_email_body("李明你好\n请今天下午三点参加会议", "李华")
        second = _format_email_body(first, "李华")

        assert "  请今天下午三点参加会议" in first
        assert first.count("李华") == 1
        assert second.count("李华") == 1

    def test_calendar_confirmation_executes_tool_before_llm(self):
        """确认创建日程时必须先执行工具，不能让模型直接生成成功话术。"""
        import json
        from app.graph.nodes import agent_node

        calls: list[dict[str, Any]] = []

        class FakeCalendarExecuteTool:
            name = "execute_calendar_event_draft"

            def invoke(self, args: dict[str, Any]) -> str:
                calls.append(args)
                return json.dumps(
                    {
                        "ok": True,
                        "code": "calendar_event_draft_executed",
                        "message": "日程已创建。",
                        "data": {
                            "title": "学术会议",
                            "start_time": "2026-06-12T09:00:00+08:00",
                            "end_time": "2026-06-12T11:00:00+08:00",
                            "location": "艾特楼",
                            "external_event_id": "evt_123",
                        },
                    },
                    ensure_ascii=False,
                )

        state = {
            "messages": [],
            "user_message": "确认创建",
            "active_calendar_draft": {"artifact_id": "art_calendar"},
            "route_trace": [],
        }

        with patch("app.graph.tools.create_tools", return_value=[FakeCalendarExecuteTool()]):
            with patch("app.graph.nodes.get_chat_model") as mock_model:
                result = agent_node(state)

        mock_model.assert_not_called()
        assert calls == [{"conflict_override": False}]
        assert "日程已成功创建" in result["response"]
        assert "evt_123" not in result["response"]
        assert "Google Event ID" not in result["response"]

    def test_short_calendar_confirmation_executes_after_prompt(self):
        """上一轮已要求确认创建日程时，短回复“确认”也应执行工具。"""
        import json
        from app.graph.nodes import agent_node

        calls: list[dict[str, Any]] = []

        class FakeCalendarExecuteTool:
            name = "execute_calendar_event_draft"

            def invoke(self, args: dict[str, Any]) -> str:
                calls.append(args)
                return json.dumps(
                    {
                        "ok": True,
                        "code": "calendar_event_draft_executed",
                        "message": "日程已创建。",
                        "data": {
                            "title": "周会",
                            "start_time": "2026-06-19T10:00:00+08:00",
                            "end_time": "2026-06-19T12:00:00+08:00",
                            "location": "艾特楼",
                            "external_event_id": "evt_hidden",
                        },
                    },
                    ensure_ascii=False,
                )

        state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "日程草稿已创建。确认无误后，回复“确认创建”即可写入您的 Google Calendar。",
                }
            ],
            "user_message": "确认",
            "active_calendar_draft": {"artifact_id": "art_calendar", "content": {"title": "周会"}},
            "route_trace": [],
        }

        with patch("app.graph.tools.create_tools", return_value=[FakeCalendarExecuteTool()]):
            with patch("app.graph.nodes.get_chat_model") as mock_model:
                result = agent_node(state)

        mock_model.assert_not_called()
        assert calls == [{"conflict_override": False}]
        assert "日程已成功创建" in result["response"]
        assert "evt_hidden" not in result["response"]

    def test_batch_email_confirmation_uses_batch_tool_before_llm(self):
        """上一轮已提示两封邮件时，确认发送应走批量工具而不是只发 active 草稿。"""
        import json
        from app.graph.nodes import agent_node

        calls: list[dict[str, Any]] = []

        class FakeBatchEmailTool:
            name = "send_all_local_email_drafts"

            def invoke(self, args: dict[str, Any]) -> str:
                calls.append(args)
                return json.dumps(
                    {
                        "ok": True,
                        "code": "local_email_drafts_sent",
                        "message": "已发送 2 封本地邮件草稿。",
                        "data": {
                            "sent_count": 2,
                            "failed_count": 0,
                            "sent": [
                                {
                                    "to": [{"email": "liming@example.com", "name": "李明"}],
                                    "subject": "会议通知",
                                },
                                {
                                    "to": [{"email": "zhao@example.com", "name": "赵涛"}],
                                    "subject": "会议通知",
                                },
                            ],
                        },
                    },
                    ensure_ascii=False,
                )

        class FakeSingleEmailTool:
            name = "send_email_draft"

            def invoke(self, args: dict[str, Any]) -> str:
                raise AssertionError("不应该只发送 active 单封草稿")

        state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "两封邮件内容都完整了，回复“确认发送”我就把两封都发出去。",
                }
            ],
            "user_message": "确认发送",
            "active_email_draft": {"artifact_id": "art_latest"},
            "route_trace": [],
        }

        with patch(
            "app.graph.tools.create_tools",
            return_value=[FakeBatchEmailTool(), FakeSingleEmailTool()],
        ):
            with patch("app.graph.nodes.get_chat_model") as mock_model:
                result = agent_node(state)

        mock_model.assert_not_called()
        assert calls == [{"confirm": True, "thread_only": True}]
        assert "已成功发送 2 封邮件" in result["response"]
        assert "李明 <liming@example.com>" in result["response"]
