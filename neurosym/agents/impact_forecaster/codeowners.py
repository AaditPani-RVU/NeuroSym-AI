import fnmatch
import os


def find_codeowners(repo_root: str) -> str | None:
    """
    Locate CODEOWNERS file in standard locations:
    1. .github/CODEOWNERS
    2. CODEOWNERS
    3. docs/CODEOWNERS
    """
    candidates = [
        os.path.join(repo_root, ".github", "CODEOWNERS"),
        os.path.join(repo_root, "CODEOWNERS"),
        os.path.join(repo_root, "docs", "CODEOWNERS"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_codeowners(text: str) -> list[tuple[str, list[str]]]:
    """
    Parse CODEOWNERS content into a list of (pattern, owners).
    Preserves order because "last match wins".
    """
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        pattern = parts[0]
        owners = parts[1:]
        rules.append((pattern, owners))
    return rules


def match_owners(file_paths: list[str], rules: list[tuple[str, list[str]]]) -> set[str]:
    """
    Determine owners for a list of file paths.
    Follows GitHub's logic: for each file, the LAST matching pattern in rules dictates the owners.
    """
    owners_set = set()

    for path in file_paths:
        # Normalize path to rely on forward slashes for matching if needed,
        # though fnmatch handles os specific separators usually.
        # GitHub CODEOWNERS always use forward slash.
        path_forward = path.replace(os.sep, "/")

        last_match_owners = None

        for pattern, owners in rules:
            # Clean pattern for comparison
            # GitHub patterns starting with / are anchored to root.
            # We assume file_paths are relative to root (no leading /).
            # So if pattern starts with /, we strip it to compare.

            clean_pattern = pattern
            if clean_pattern.startswith("/"):
                clean_pattern = clean_pattern[1:]

            matched = False

            # 1. Directory match (pattern ends with /)
            # e.g. "docs/" matches "docs/foo.md"
            if pattern.endswith("/"):
                if path_forward.startswith(clean_pattern):
                    matched = True

            # 2. Recursive wildcard implied?
            # If pattern has no slash (and not *), it matches in any depth?
            # e.g. "*.js" matches "a/b/c.js". "docs/" matches "foo/docs/" too if not anchored?
            # GitHub: "If the pattern does not start with /, it is treated as if it implies **/"
            # However, if it starts with *, it matches simply.

            # Simple fnmatch check on the clean pattern
            if not matched:
                if fnmatch.fnmatch(path_forward, clean_pattern):
                    matched = True

            # 3. Handle unanchored wildcard prefix logic (e.g. "start w/o slash")
            # If pattern is "utils/", it matches "src/utils/" too.
            if not matched and not pattern.startswith("/"):
                # Try matching as **/pattern
                if fnmatch.fnmatch(path_forward, "**/" + pattern):
                    matched = True
                # Or if it is a directory pattern, check if path contains it as segment
                if pattern.endswith("/") and ("/" + pattern) in path_forward:
                    matched = True

            if matched:
                last_match_owners = owners

        if last_match_owners:
            owners_set.update(last_match_owners)

    return owners_set
