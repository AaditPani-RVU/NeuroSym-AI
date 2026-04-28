import unittest

from neurosym.agents.impact_forecaster import arch_map, codeowners


class TestCodeOwners(unittest.TestCase):
    def test_basic_match(self):
        content = """
        * @global-owner
        /docs/ @docs-team
        src/ @dev-team
        """
        rules = codeowners.parse_codeowners(content)

        # Test 1: Global fallback
        self.assertEqual(codeowners.match_owners(["README.md"], rules), {"@global-owner"})

        # Test 2: Specific override
        self.assertEqual(codeowners.match_owners(["docs/api.md"], rules), {"@docs-team"})

        # Test 3: Last match wins order check (if we had conflicting rules)
        # Re-parse simple conflict
        conflict_rules = codeowners.parse_codeowners("* @a\n* @b")
        self.assertEqual(codeowners.match_owners(["file.txt"], conflict_rules), {"@b"})


class TestArchMap(unittest.TestCase):
    def test_chain_building(self):
        # auth changes -> frontend is impacted because frontend depends on auth?
        # definition: auth depends_on ["frontend"] means auth needs frontend?
        # Usually "A depends on B" means if B changes, A is impacted.
        # My implementation: ImpactEdge(src=impacted, dst=dependent).
        # In arch_map.py:
        #   for candidate in arch_map: if impacted in candidate.depends_on: edges.append(...)

        # Scenario:
        # API Layer changes.
        # UI Layer depends on API Layer.

        # arch_map entry for UI: depends_on: ["API"]
        # modified: API
        # impacted set: {API}
        # loop candidate UI: "API" is in UI.depends_on -> True.
        # Edge: API -> UI.

        # Let's verify data struct
        # Test map where B depends on A
        b_def = arch_map.ComponentDef("B", ["b.py"], ["A"], [])
        a_def = arch_map.ComponentDef("A", ["a.py"], [], [])

        # This means B matches if b.py changes.
        # Wait, dependency logic:
        # If I change A, does B break? Yes, because B depends on A.
        # So "components impacted by change in A" should include B.

        am = {"A": a_def, "B": b_def}

        # Change in A
        chain = arch_map.build_impact_chain(["A"], am)

        # We expect edge A -> B
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].src, "A")
        self.assertEqual(chain[0].dst, "B")


if __name__ == "__main__":
    unittest.main()
