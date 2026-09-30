"""LangGraph orchestrator: must behave exactly like the plain-Python orchestrator."""

from __future__ import annotations

import os
import threading
import unittest
from unittest.mock import MagicMock, patch

from agents import orchestrator
from agents.langgraph_orchestrator import (
    build_retailask_graph,
    retailask_graph_mermaid,
    run_langgraph_question,
)
from tests import test_orchestrator as base


class LangGraphRunsOrchestratorSuite(base.OrchestratorUnitTests):
    """Every plain-orchestrator test, re-run with the LangGraph engine."""

    def setUp(self):
        patcher = patch.object(base, 'run_supervised_question', run_langgraph_question)
        patcher.start()
        self.addCleanup(patcher.stop)


class LangGraphSpecificTests(unittest.TestCase):
    def test_graph_has_expected_nodes(self):
        graph = build_retailask_graph(
            route_fn=MagicMock(), sql_agent_fn=MagicMock(), graph_agent_fn=MagicMock()
        )
        nodes = set(graph.get_graph().nodes)
        self.assertTrue(
            {
                'supervisor',
                'general_agent',
                'sql_agent',
                'graph_agent',
                'sql_agent_for_synthesis',
                'graph_agent_for_synthesis',
                'synthesize',
            }
            <= nodes
        )

    def test_sql_and_graph_agents_run_in_parallel(self):
        # Each agent waits for the other; sequential execution would time out.
        barrier = threading.Barrier(2, timeout=5)

        def sql_agent(q, **_kwargs):
            barrier.wait()
            return base._sql_ok(q)

        def graph_agent(q):
            barrier.wait()
            return base._graph_ok(q)

        result = run_langgraph_question(
            'Which high-selling products also have negative feedback?',
            route_fn=lambda q: {'route': 'sql_and_graph', 'reason': 'both', 'question': q},
            sql_agent_fn=sql_agent,
            graph_agent_fn=graph_agent,
            synthesize_fn=lambda q, s, g, **_: 'merged',
        )
        self.assertTrue(result['results']['sql']['success'])
        self.assertTrue(result['results']['graph']['success'])
        self.assertEqual(result['answer'], 'merged')
        self.assertTrue(result['success'])

    def test_mermaid_diagram_lists_routes(self):
        diagram = retailask_graph_mermaid()
        for node in ('supervisor', 'sql_agent', 'graph_agent', 'synthesize'):
            self.assertIn(node, diagram)

    def test_empty_question(self):
        result = run_langgraph_question('   ')
        self.assertEqual(result['error'], 'empty_question')


class RunQuestionDispatchTests(unittest.TestCase):
    def test_langgraph_is_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ORCHESTRATOR', None)
            self.assertEqual(orchestrator.active_orchestrator(), 'langgraph')

    def test_python_engine_selectable(self):
        with patch.dict(os.environ, {'ORCHESTRATOR': 'python'}):
            self.assertEqual(orchestrator.active_orchestrator(), 'python')
            with patch.object(orchestrator, 'run_supervised_question', return_value={'ok': 1}) as plain:
                self.assertEqual(orchestrator.run_question('q'), {'ok': 1})
            plain.assert_called_once_with('q')

    def test_langgraph_engine_used_by_run_question(self):
        with patch.dict(os.environ, {'ORCHESTRATOR': 'langgraph'}):
            with patch(
                'agents.langgraph_orchestrator.run_langgraph_question',
                return_value={'engine': 'lg'},
            ) as lg:
                self.assertEqual(orchestrator.run_question('q'), {'engine': 'lg'})
            lg.assert_called_once_with('q')


if __name__ == '__main__':
    unittest.main()
