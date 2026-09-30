"""
Supervisor + agent orchestration as a LangGraph StateGraph.

Same behaviour and result shape as orchestrator.run_supervised_question, but the
workflow is an explicit graph: the Supervisor node picks a route through a
conditional edge, and for `sql_and_graph` the SQL and Graph agents run in
parallel before a join into the synthesis node.

    START → supervisor ─┬─ general ──────────→ general_agent ──────────────→ END
                        ├─ sql ──────────────→ sql_agent ──────────────────→ END
                        ├─ graph ────────────→ graph_agent ────────────────→ END
                        └─ sql_and_graph ─┬─→ sql_agent_for_synthesis ───┐
                                          └─→ graph_agent_for_synthesis ─┴→ synthesize → END
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .orchestrator import (
    GraphAgentFn,
    LLMCall,
    RouteFn,
    SqlAgentFn,
    _safe_run_agent,
    empty_question_result,
    general_result,
    resolve_dependencies,
    resolve_routing,
    single_agent_result,
    sql_and_graph_result,
)

logger = logging.getLogger('retail-agent')

ROUTE_TO_NODES = {
    'general': ['general_agent'],
    'sql': ['sql_agent'],
    'graph': ['graph_agent'],
    'sql_and_graph': ['sql_agent_for_synthesis', 'graph_agent_for_synthesis'],
}


class RetailAskState(TypedDict, total=False):
    question: str
    routing: dict[str, Any]
    route: str
    sql_result: dict[str, Any]
    graph_result: dict[str, Any]
    result: dict[str, Any]


def build_retailask_graph(
    *,
    route_fn: RouteFn | None = None,
    sql_agent_fn: SqlAgentFn | None = None,
    graph_agent_fn: GraphAgentFn | None = None,
    llm_call: LLMCall | None = None,
    synthesize_fn: Callable[..., str] | None = None,
):
    route_fn, sql_agent_fn, graph_agent_fn, synthesize_fn = resolve_dependencies(
        route_fn, sql_agent_fn, graph_agent_fn, synthesize_fn
    )

    def supervisor(state: RetailAskState) -> RetailAskState:
        routing, route = resolve_routing(state['question'], route_fn)
        return {'routing': routing, 'route': route}

    def general_agent(state: RetailAskState) -> RetailAskState:
        return {'result': general_result(state['question'], state['routing'])}

    def sql_agent(state: RetailAskState) -> RetailAskState:
        q = state['question']
        sql_result = _safe_run_agent('sql', sql_agent_fn, q)
        return {'result': single_agent_result(q, state['routing'], 'sql', sql_result)}

    def graph_agent(state: RetailAskState) -> RetailAskState:
        q = state['question']
        graph_result = _safe_run_agent('graph', graph_agent_fn, q)
        return {'result': single_agent_result(q, state['routing'], 'graph', graph_result)}

    def sql_agent_for_synthesis(state: RetailAskState) -> RetailAskState:
        # Raw rows only; the synthesis node phrases the final answer.
        return {
            'sql_result': _safe_run_agent(
                'sql', sql_agent_fn, state['question'], explain_rows=False
            )
        }

    def graph_agent_for_synthesis(state: RetailAskState) -> RetailAskState:
        return {'graph_result': _safe_run_agent('graph', graph_agent_fn, state['question'])}

    def synthesize(state: RetailAskState) -> RetailAskState:
        return {
            'result': sql_and_graph_result(
                state['question'],
                state['routing'],
                state['sql_result'],
                state['graph_result'],
                synthesize_fn,
                llm_call=llm_call,
            )
        }

    def pick_route(state: RetailAskState) -> list[str]:
        return ROUTE_TO_NODES[state['route']]

    builder = StateGraph(RetailAskState)
    builder.add_node('supervisor', supervisor)
    builder.add_node('general_agent', general_agent)
    builder.add_node('sql_agent', sql_agent)
    builder.add_node('graph_agent', graph_agent)
    builder.add_node('sql_agent_for_synthesis', sql_agent_for_synthesis)
    builder.add_node('graph_agent_for_synthesis', graph_agent_for_synthesis)
    builder.add_node('synthesize', synthesize)

    builder.add_edge(START, 'supervisor')
    builder.add_conditional_edges(
        'supervisor',
        pick_route,
        [node for nodes in ROUTE_TO_NODES.values() for node in nodes],
    )
    builder.add_edge('general_agent', END)
    builder.add_edge('sql_agent', END)
    builder.add_edge('graph_agent', END)
    builder.add_edge(['sql_agent_for_synthesis', 'graph_agent_for_synthesis'], 'synthesize')
    builder.add_edge('synthesize', END)
    return builder.compile()


_default_graph = None


def _get_default_graph():
    global _default_graph
    if _default_graph is None:
        _default_graph = build_retailask_graph()
    return _default_graph


def run_langgraph_question(
    question: str,
    *,
    route_fn: RouteFn | None = None,
    sql_agent_fn: SqlAgentFn | None = None,
    graph_agent_fn: GraphAgentFn | None = None,
    llm_call: LLMCall | None = None,
    synthesize_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Drop-in replacement for run_supervised_question, executed by LangGraph."""
    q = (question or '').strip()
    if not q:
        return empty_question_result()

    injected = (route_fn, sql_agent_fn, graph_agent_fn, llm_call, synthesize_fn)
    if any(dep is not None for dep in injected):
        graph = build_retailask_graph(
            route_fn=route_fn,
            sql_agent_fn=sql_agent_fn,
            graph_agent_fn=graph_agent_fn,
            llm_call=llm_call,
            synthesize_fn=synthesize_fn,
        )
    else:
        graph = _get_default_graph()

    logger.info('LangGraph run start | question=%s', q)
    final_state = graph.invoke({'question': q})
    return final_state['result']


def retailask_graph_mermaid() -> str:
    """Mermaid diagram of the compiled graph (for README / demo)."""
    return build_retailask_graph(
        route_fn=lambda q: {'route': 'general', 'reason': '', 'question': q},
        sql_agent_fn=lambda q, **_: {},
        graph_agent_fn=lambda q: {},
        synthesize_fn=lambda *a, **k: '',
    ).get_graph().draw_mermaid()
