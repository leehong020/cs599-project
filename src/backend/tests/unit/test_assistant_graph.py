import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from app.main import create_app
from app.graph.builder import (
    build_assistant_graph,
    export_assistant_mermaid,
    export_calendar_subgraph_mermaid,
    export_mail_subgraph_mermaid,
)
from app.graph.runner import DEFAULT_RECURSION_LIMIT, build_thread_config
from app.graph.subgraphs import run_calendar_subgraph_once, run_mail_subgraph_once
from app.graph.tasks import compile_request_tasks, extract_contact_mentions, schedule_task_batches


def _mock_llm():
    """构造不会访问外部模型的测试 LLM。"""
    llm = MagicMock()
    msg = MagicMock()
    msg.content = "已理解请求，并完成对应 Agent 处理。"
    msg.tool_calls = []
    llm.invoke.return_value = msg
    llm.bind_tools.return_value = llm
    return llm


def test_assistant_graph_compiles_and_exports_mermaid() -> None:
    graph = build_assistant_graph()
    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        result = graph.invoke(
            {"thread_id": "thread_graph", "user_message": "帮我安排会议并发送会议链接邮件"},
            config=build_thread_config("thread_graph"),
        )
    mermaid = export_assistant_mermaid()

    assert isinstance(result["response"], str) and len(result["response"]) > 10
    # LLM 回复应该是自然语言，不是硬编码模板文本
    assert "已编译成" not in result["response"]
    assert result["node_timings"][0]["node"] == "state_loader"
    assert all(item["duration_ms"] >= 0 for item in result["node_timings"])
    assert "state_loader" in mermaid
    assert "supervisor_agent" in mermaid
    assert "mail_agent" in mermaid
    assert "calendar_agent" in mermaid
    assert "response_agent" in mermaid


def test_general_chat_reuses_supervisor_direct_response() -> None:
    """普通聊天由 Supervisor 的自然回复承接，避免 Response Agent 再次调用模型。"""
    graph = build_assistant_graph()
    llm = MagicMock()
    msg = MagicMock()
    msg.content = (
        '{"intent":"general_chat","summary":"用户在打招呼",'
        '"route_agents":["response_agent"],'
        '"direct_response":"你好呀，我在。你想先聊聊，还是让我帮你处理邮件或日程？",'
        '"reason":"普通问候不需要调用邮件或日程工具"}'
    )
    msg.tool_calls = []
    llm.invoke.return_value = msg

    with patch("app.services.llm_client.get_chat_model", return_value=llm):
        result = graph.invoke(
            {"thread_id": "thread_general_chat", "user_message": "你好"},
            config=build_thread_config("thread_general_chat"),
        )

    assert result["response"] == "你好呀，我在。你想先聊聊，还是让我帮你处理邮件或日程？"
    assert result["supervisor_plan"]["route_agents"] == ["response_agent"]
    assert llm.invoke.call_count == 1


def test_response_agent_context_does_not_expose_stale_active_draft_details() -> None:
    """最终回复模型不应看到无关旧草稿详情，避免主动汇总旧任务。"""
    from app.graph.agents.runtime import AgentRunResult
    from app.graph.multi_nodes import response_agent

    captured: dict[str, str] = {}

    def fake_run_llm_agent(**kwargs):
        captured["agent_input"] = kwargs["agent_input"]
        return AgentRunResult(
            agent_name="response_agent",
            content="已为你生成明天下午 5 点到 6 点的学术会议日程草稿，请确认是否创建。",
        )

    state = {
        "messages": [],
        "user_message": "创建一个日程通知我明天下午5点到6点有一个学术会议需要参加",
        "supervisor_plan": {"route_agents": ["calendar_agent"], "summary": "创建新日程"},
        "calendar_result": {"content": "日程草稿已创建"},
        "execution_result": {"status": "none"},
        "active_email_draft": {
            "subject": "会议时间变更通知",
            "body": "这是上一轮未发送邮件，不属于本轮任务。",
        },
        "active_calendar_draft": {
            "title": "旧学术会议",
            "start_time": "2026-06-12T09:00:00+08:00",
        },
        "route_trace": [],
    }

    with patch("app.graph.multi_nodes.run_llm_agent", side_effect=fake_run_llm_agent):
        result = response_agent(state)

    assert "会议时间变更通知" not in captured["agent_input"]
    assert "旧学术会议" not in captured["agent_input"]
    assert "has_active_email_draft" in captured["agent_input"]
    assert "已为你生成明天下午" in result["response"]


def test_mail_and_calendar_subgraphs_run_independently() -> None:
    tasks = compile_request_tasks("安排会议并发送邮件")
    mail_result = run_mail_subgraph_once(tasks)
    calendar_result = run_calendar_subgraph_once(tasks)

    assert any(item["domain"] == "mail" for item in mail_result["task_results"])
    assert any(item["domain"] == "calendar" for item in calendar_result["task_results"])
    assert "plan_mail_task" in export_mail_subgraph_mermaid()
    assert "plan_calendar_task" in export_calendar_subgraph_mermaid()


def test_multiple_people_are_parsed_from_user_turn() -> None:
    mentions = extract_contact_mentions("请给张三、李四发送项目邮件")

    assert mentions == ["张三", "李四"]


def test_agent_graph_keeps_contact_context_without_crashing() -> None:
    """当前 agent+tools 架构暂不做确定性联系人消歧，但不能因同名联系人崩溃。"""
    graph = build_assistant_graph()
    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        result = graph.invoke(
            {
                "thread_id": "thread_contacts",
                "user_message": "给张三发送邮件",
                "available_contacts": [
                    {"id": "c1", "display_name": "张三", "email": "sales@example.com"},
                    {"id": "c2", "display_name": "张三", "email": "ops@example.com"},
                ],
            },
            config=build_thread_config("thread_contacts"),
        )

    assert isinstance(result["response"], str)
    assert result["messages"][-2]["content"] == "给张三发送邮件"
    assert result["available_contacts"][0]["email"] == "sales@example.com"


def test_task_dag_parallel_and_sequential_batches() -> None:
    independent = compile_request_tasks("安排会议并发送邮件")
    dependent = compile_request_tasks("安排会议，然后发送会议链接邮件")

    assert schedule_task_batches(independent) == [["task_calendar_1", "task_mail_1"]]
    assert schedule_task_batches(dependent) == [["task_calendar_1"], ["task_mail_1"]]


def test_thread_id_checkpoint_recovers_after_graph_rebuild(tmp_path) -> None:
    db_path = tmp_path / "langgraph.sqlite3"
    first_connection = sqlite3.connect(db_path, check_same_thread=False)
    first_graph = build_assistant_graph(checkpointer=SqliteSaver(first_connection))
    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        first = first_graph.invoke(
            {"thread_id": "thread_restore", "user_message": "帮我安排会议"},
            config=build_thread_config("thread_restore"),
        )
    first_connection.close()

    second_connection = sqlite3.connect(db_path, check_same_thread=False)
    second_graph = build_assistant_graph(checkpointer=SqliteSaver(second_connection))
    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        second = second_graph.invoke(
            {"user_message": "再发送一封邮件"},
            config=build_thread_config("thread_restore"),
        )
    restored = second_graph.get_state(config=build_thread_config("thread_restore")).values
    second_connection.close()

    assert first["turn_count"] == 1
    assert second["turn_count"] == 2
    assert len(restored["messages"]) == 4


def test_recursion_limit_is_part_of_thread_config() -> None:
    config = build_thread_config("thread_limit")

    assert config["recursion_limit"] == DEFAULT_RECURSION_LIMIT
    assert config["configurable"]["thread_id"] == "thread_limit"


def test_cycle_in_task_dag_is_rejected() -> None:
    with pytest.raises(ValueError):
        schedule_task_batches(
            [
                {
                    "id": "a",
                    "domain": "mail",
                    "title": "A",
                    "depends_on": ["b"],
                    "status": "planned",
                    "reason": None,
                },
                {
                    "id": "b",
                    "domain": "calendar",
                    "title": "B",
                    "depends_on": ["a"],
                    "status": "planned",
                    "reason": None,
                },
            ]
        )


def test_assistant_turn_stream_emits_progress_and_final() -> None:
    client = TestClient(create_app())

    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        with client.stream(
            "POST",
            "/api/assistant/turn/stream",
            json={"thread_id": "thread_stream", "message": "安排会议"},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: progress" in body
    assert "event: final" in body
    assert ("正在加载" in body or "正在理解" in body or "正在生成" in body)


def test_assistant_graph_mermaid_api_exports_main_and_subgraphs() -> None:
    client = TestClient(create_app())

    main_response = client.get("/api/assistant/graph/mermaid")
    mail_response = client.get("/api/assistant/subgraphs/mail/mermaid")
    calendar_response = client.get("/api/assistant/subgraphs/calendar/mermaid")

    assert main_response.status_code == 200
    assert "state_loader" in main_response.json()["mermaid"]
    assert "supervisor_agent" in main_response.json()["mermaid"]
    assert mail_response.status_code == 200
    assert "plan_mail_task" in mail_response.json()["mermaid"]
    assert calendar_response.status_code == 200
    assert "plan_calendar_task" in calendar_response.json()["mermaid"]


def test_assistant_turn_api_returns_node_timings() -> None:
    client = TestClient(create_app())

    with patch("app.services.llm_client.get_chat_model", return_value=_mock_llm()):
        response = client.post(
            "/api/assistant/turn",
            json={"thread_id": "thread_timing_api", "message": "安排会议"},
        )

    assert response.status_code == 200
    assert response.json()["node_timings"][0]["node"] == "state_loader"
