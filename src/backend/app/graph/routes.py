"""图路由 —— agent 内部处理工具调用，不需要条件路由。"""


def route_after_agent(state) -> str:
    """保留兼容。agent 节点内部已处理所有路由逻辑。"""
    return "save_turn"
