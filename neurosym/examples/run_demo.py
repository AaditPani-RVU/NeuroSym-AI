import os
import sys

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir = .../neurosym/examples
# parent = .../neurosym
# grandparent = .../neurosym-ai
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from neurosym.agents.impact_forecaster import GitHubAdapter  # noqa: E402

print(f"Debug: current_dir={current_dir}")
print(f"Debug: project_root={project_root}")
print(f"Debug: sys.path[0]={sys.path[0]}")

try:
    import neurosym

    print(f"Debug: neurosym file={neurosym.__file__}")
except ImportError as e:
    print(f"Debug: Failed to import neurosym: {e}")

try:
    import neurosym.agents

    print(f"Debug: neurosym.agents file={neurosym.agents.__file__}")
except ImportError as e:
    print(f"Debug: Failed to import neurosym.agents: {e}")

# Uses FallbackLLM if standard not available, or we mock it.
# We'll stick to symbolic parts mainly if no LLM configured,
# but GitHubAdapter defaults to no LLM if none passed.


def run_demo():
    repo_path = os.path.join(current_dir, "dummy-repo-1")
    print(f"Running Impact Forecast on: {repo_path}")

    # Initialize Adapter
    # We won't pass an LLM here to keep it deterministic for the demo,
    # or we could use a mock.
    adapter = GitHubAdapter(repo_root=repo_path)

    # Simulate a PR
    # PR touches auth/login.py and api/v1/users.py
    pr_url = "https://github.com/AaditPani-RVU/dummy-repo-1/pull/999"

    simulated_files = ["auth/login_service.py", "api/v1/user_routes.py"]

    simulated_diff = """
diff --git a/auth/login_service.py b/auth/login_service.py
index abc..def 100644
--- a/auth/login_service.py
+++ b/auth/login_service.py
@@ -10,6 +10,7 @@ def login(user, password):
     if verify(user, password):
         token = generate_token(user)
+        # Added specialized logging
         return token
     return None

diff --git a/api/v1/user_routes.py b/api/v1/user_routes.py
index 111..222 100644
--- a/api/v1/user_routes.py
+++ b/api/v1/user_routes.py
@@ -20,4 +20,5 @@ def get_user(id):
     return db.find_user(id)
+    # Updated route handler
"""

    print("\n--- Simulating PR ---")
    print(f"URL: {pr_url}")
    print(f"Files: {simulated_files}")

    forecast = adapter.generate_forecast(
        pr_url, diff_content=simulated_diff, file_list=simulated_files
    )

    print("\n--- Forecast Result ---")
    print(forecast.model_dump_json(indent=2))

    # Minimal assertions for the demo
    print("\n--- Checks ---")
    if "security.auth" in forecast.triggered_rules:
        print("[PASS] Security/Auth rule triggered")
    else:
        print("[FAIL] Security/Auth rule MISSED")

    if "@security-team" in forecast.owners_to_notify:
        print("[PASS] @security-team notified (via CODEOWNERS/ArchMap)")
    else:
        print("[FAIL] @security-team NOT notified")

    # Check impact chain: auth_service changed.
    # payment_service depends on auth_service.
    # public_api depends on payment_service AND auth_service.
    # So both should be in chain?
    # Our simple logic:
    #   Impacted components: auth_service (due to auth/ path), public_api (due to api/ path)
    #   Chain:
    #     auth_service -> payment_service
    #     auth_service -> public_api
    #     public_api -> (nothing depends on it in our map)

    chain_srcs = [e.src for e in forecast.impact_chain]
    chain_dsts = [e.dst for e in forecast.impact_chain]

    if "auth_service" in chain_srcs and "payment_service" in chain_dsts:
        print("[PASS] Impact Chain detected: auth_service -> payment_service")
    else:
        print(f"[FAIL] Chain missing auth->payment. Chain: {forecast.impact_chain}")


if __name__ == "__main__":
    run_demo()
