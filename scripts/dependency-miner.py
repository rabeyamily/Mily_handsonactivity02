#!/usr/bin/env python3
"""
Dependency Miner - Mine commits for dependency version changes using PyDriller

Usage:
    python dependency-miner.py <owner> <repo>

Example:
    python dependency-miner.py pac4j dropwizard-pac4j

Requirements:
    pip install pydriller python-dotenv
"""

import csv
import re
import sys
from pydriller import Repository
import os
from lxml import etree


def _parse_pom_dependencies(pom_xml_text):
    """Extract dependencies from pom.xml text and return a dict of groupId:artifactId -> version.

    This function uses lxml to parse the XML content of a pom.xml file and extract the dependencies. It handles XML namespaces if present. The result is a dictionary where the key is "groupId:artifactId" and the value is the version string. If the pom.xml text is empty or None, it returns an empty dictionary. You can use it to parse a complete pom.xml file content. Use or delete.
    """
    if not pom_xml_text:
        return {}

    tree = etree.fromstring(pom_xml_text.encode())

    # Extract namespace if present (pom.xml files often have a default namespace)
    nsmap = tree.nsmap
    namespace = nsmap.get(None)  # default namespace

    dependencies = {}

    if namespace:
        ns = {"m": namespace}
        dep_path = ".//m:dependency"
        group_path = "m:groupId"
        artifact_path = "m:artifactId"
        version_path = "m:version"
    else:
        ns = None
        dep_path = ".//dependency"
        group_path = "groupId"
        artifact_path = "artifactId"
        version_path = "version"

    for dep in tree.findall(dep_path, namespaces=ns):
        group = dep.find(group_path, namespaces=ns)
        artifact = dep.find(artifact_path, namespaces=ns)
        version = dep.find(version_path, namespaces=ns)

        if group is None or artifact is None:
            continue  # skip malformed dependencies

        group_id = group.text.strip()
        artifact_id = artifact.text.strip()
        version_text = version.text.strip() if version is not None else None

        key = f"{group_id}:{artifact_id}"
        dependencies[key] = version_text

    return dependencies


def _parse_dependency_blocks(pom_xml_text):
    """
    Parse XML text for <dependency> blocks and return dict of groupId:artifactId -> version.

    This helper function is provided to help you parse Maven pom.xml files. You can use it or delete if you don't need it. It uses regular expressions to find all <dependency> blocks and extract the groupId, artifactId, and version. The result is a dictionary where the key is "groupId:artifactId" and the value is the version string.
    """
    deps = {}
    if not pom_xml_text or not pom_xml_text.strip():
        return deps
    # Find all <dependency>...</dependency> blocks (non-greedy, allow newlines)
    for block in re.findall(r"<dependency>(.*?)</dependency>", pom_xml_text, re.DOTALL):
        g = re.search(r"<groupId>([^<]+)</groupId>", block)
        a = re.search(r"<artifactId>([^<]+)</artifactId>", block)
        v = re.search(r"<version>([^<]+)</version>", block)
        if g and a and v:
            key = f"{g.group(1).strip()}:{a.group(1).strip()}"
            deps[key] = v.group(1).strip()
    return deps


def mine_repository(owner: str, repo: str) -> None:
    """
    Main function to mine repository for dependency changes.

    Args:
        owner: Repository owner (e.g., 'pac4j')
        repo: Repository name (e.g., 'dropwizard-pac4j')
    """
    repo_url = f"https://github.com/{owner}/{repo}"

    print(f"Analyzing repository: {owner}/{repo}")
    print(f"URL: {repo_url}")
    print("This may take a few minutes...\n")

    # Get commits with dependency changes
    # TODO: implement the neded logic to analyze commits and extract dependency changes. Use helper functions as needed and write your own helper functions.
    repo_url = f"{repo_url}.git"
    rows = []
    seen = set()
    for commit in Repository(repo_url, only_modifications_with_file_types=[".xml"]).traverse_commits():
        for f in commit.modified_files:
            if f.filename != "pom.xml":
                continue
            before = _parse_dependency_blocks(f.source_code_before) or {}
            after = _parse_dependency_blocks(f.source_code) or {}
            for k in after:
                if k not in before:
                    rows.append((commit.hash, commit.author_date, commit.author.name, k, "added"))
                    seen.add(commit.hash)
                elif before[k] != after[k]:
                    rows.append((commit.hash, commit.author_date, commit.author.name, k, "changed from " + str(before.get(k, "")) + " to " + str(after.get(k, ""))))
                    seen.add(commit.hash)
            for k in before:
                if k not in after:
                    rows.append((commit.hash, commit.author_date, commit.author.name, k, "removed"))
                    seen.add(commit.hash)
    output_filename = f"{owner}_{repo}_dependency_commits.csv"
    with open(output_filename, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["Commit Hash", "Commit Date", "Commit Author", "Dependency Name", "Type of Change"])
        for r in rows:
            w.writerow([r[0], str(r[1]), r[2], r[3], r[4]])
    commits_with_changes = seen

    # Display results
    print(f"Repository: {owner}/{repo}")
    print("Results:")
    print(f"Number of commits with dependency changes: {len(commits_with_changes)}")
    print(f"Commit list saved to: {output_filename}")


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 3:
        print("Usage: python dependency-miner.py <owner> <repo>")
        print("Example: python dependency-miner.py pac4j dropwizard-pac4j")
        sys.exit(1)

    owner = sys.argv[1]
    repo = sys.argv[2]

    mine_repository(owner, repo)


if __name__ == "__main__":
    main()
