from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes.route import route_query
from app.agent.nodes.retrieve_context import retrieve_context
from app.agent.nodes.roleplay import roleplay
from app.agent.nodes.answer import answer
from app.agent.nodes.oss_finder import oss_finder
from app.agent.nodes.oss_solver import oss_solver


def needs_context(state: AgentState) -> str:
    return "retrieve_context" if state["route"] in ("roleplay", "answer") else state["route"]


def after_context(state: AgentState) -> str:
    return state["route"]


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("route", route_query)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("roleplay", roleplay)
    graph.add_node("answer", answer)
    graph.add_node("oss_finder", oss_finder)
    graph.add_node("oss_solver", oss_solver)

    graph.set_entry_point("route")

    graph.add_conditional_edges(
        "route",
        needs_context,
        {
            "retrieve_context": "retrieve_context",
            "oss_finder": "oss_finder",
            "oss_solver": "oss_solver",
        },
    )

    graph.add_conditional_edges(
        "retrieve_context",
        after_context,
        {
            "roleplay": "roleplay",
            "answer": "answer",
        },
    )

    graph.add_edge("roleplay", END)
    graph.add_edge("answer", END)
    graph.add_edge("oss_finder", END)
    graph.add_edge("oss_solver", END)

    return graph.compile()


_compiled = None


def get_agent():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
