from langgraph.graph import END, START, StateGraph

from app.graph.edges import route_after_review, route_after_router
from app.graph.nodes import rag_search_node, review_node, router_node, save_to_db_node
from app.graph.state import InquiryState


def build_graph():
    workflow = StateGraph(InquiryState)

    workflow.add_node("initial_save", save_to_db_node)
    workflow.add_node("rag_search", rag_search_node)
    workflow.add_node("router", router_node)
    workflow.add_node("review", review_node)
    workflow.add_node("final_save", save_to_db_node)

    workflow.add_edge(START, "initial_save")
    workflow.add_edge("initial_save", "rag_search")
    workflow.add_edge("rag_search", "router")

    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {"review": "review", "save_to_db": "final_save"},
    )
    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {"router": "router", "save_to_db": "final_save"},
    )

    workflow.add_edge("final_save", END)

    return workflow.compile()


graph = build_graph()
