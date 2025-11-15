#!/usr/bin/env python3
"""
Generate API documentation from cached API responses
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set


def infer_type(value: Any) -> str:
    """Infer the type of a value"""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        # Check for date formats
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return "date"
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
            return "datetime"
        if value.startswith("http://") or value.startswith("https://"):
            return "url"
        return "string"
    if isinstance(value, list):
        if not value:
            return "array"
        # Get types of first few items
        item_types = set(infer_type(item) for item in value[:3])
        if len(item_types) == 1:
            return f"array<{item_types.pop()}>"
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def extract_endpoint_info(filename: str) -> Dict[str, str]:
    """Extract endpoint information from filename"""
    # Remove timestamp and extension
    name = re.sub(r"_\d{8}_\d{6}\.json$", "", filename)

    # Convert to endpoint path
    if name == "oauth_token":
        return {"path": "/oauth/token", "method": "POST", "name": "OAuth Token"}

    if name.startswith("v3_"):
        # Replace _ID and _UUID with path parameters
        path = "/" + name.replace("_", "/")
        path = re.sub(r"/ID(?=/|$)", "/{id}", path)
        path = re.sub(r"/UUID(?=/|$)", "/{id}", path)

        # Create human-readable name
        endpoint_name = name.replace("v3_", "").replace("_", " ").title()
        endpoint_name = re.sub(r"\bId\b", "ID", endpoint_name)

        return {"path": path, "method": "GET", "name": endpoint_name}

    # Legacy format
    if "meets" in name:
        if name == "meets_list":
            return {"path": "/v3/meets", "method": "GET", "name": "List Meets"}
        if name.startswith("meet_"):
            return {
                "path": "/v3/meets/{id}",
                "method": "GET",
                "name": "Get Meet Details",
            }

    return {"path": "unknown", "method": "GET", "name": name}


def analyze_attributes(data: Any) -> Dict[str, Set[str]]:
    """Analyze attributes and their types from data"""
    attr_types = defaultdict(set)

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]

        # Handle both single object and array
        items = data if isinstance(data, list) else [data]

        for item in items:
            if isinstance(item, dict) and "attributes" in item:
                for key, value in item["attributes"].items():
                    attr_types[key].add(infer_type(value))

    return attr_types


def analyze_relationships(data: Any) -> Set[str]:
    """Analyze relationships from data"""
    relationships = set()

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]

        # Handle both single object and array
        items = data if isinstance(data, list) else [data]

        for item in items:
            if isinstance(item, dict) and "relationships" in item:
                relationships.update(item["relationships"].keys())

    return relationships


def generate_documentation():
    """Generate API documentation from cached responses"""
    cache_dir = Path("api_cache")
    if not cache_dir.exists():
        print("❌ api_cache/ directory not found")
        return

    # Group files by endpoint
    endpoints = defaultdict(list)

    for cache_file in sorted(cache_dir.glob("*.json")):
        endpoint_info = extract_endpoint_info(cache_file.name)
        endpoint_key = endpoint_info["path"]
        endpoints[endpoint_key].append((cache_file, endpoint_info))

    # Generate markdown documentation
    output = []
    output.append("# Swimtopia API Documentation")
    output.append("")
    output.append(
        "This documentation is automatically generated from cached API responses."
    )
    output.append("")
    output.append("## Base URL")
    output.append("")
    output.append("```")
    output.append("https://api.swimtopia.org")
    output.append("```")
    output.append("")
    output.append("## Authentication")
    output.append("")
    output.append(
        "All API requests (except `/oauth/token`) require an OAuth 2.0 access token."
    )
    output.append("")
    output.append("**Header:**")
    output.append("```")
    output.append("Authorization: Bearer {access_token}")
    output.append("```")
    output.append("")
    output.append("## Content Type")
    output.append("")
    output.append(
        "All responses follow the JSON:API specification (application/vnd.api+json)."
    )
    output.append("")
    output.append("---")
    output.append("")

    # Document each endpoint
    for endpoint_path in sorted(endpoints.keys()):
        files_info = endpoints[endpoint_path]
        first_file, endpoint_info = files_info[0]

        output.append(f"## {endpoint_info['name']}")
        output.append("")
        output.append(f"**{endpoint_info['method']}** `{endpoint_info['path']}`")
        output.append("")

        # Analyze all files for this endpoint to get complete attribute list
        all_attr_types = defaultdict(set)
        all_relationships = set()
        example_data = None

        for cache_file, _ in files_info:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if example_data is None:
                        example_data = data

                    # Merge attribute types
                    attr_types = analyze_attributes(data)
                    for key, types in attr_types.items():
                        all_attr_types[key].update(types)

                    # Merge relationships
                    all_relationships.update(analyze_relationships(data))

            except (json.JSONDecodeError, Exception) as e:
                print(f"  Warning: Error processing {cache_file}: {e}")
                continue

        # Document attributes
        if all_attr_types:
            output.append("### Attributes")
            output.append("")
            output.append("| Attribute | Type | Description |")
            output.append("|-----------|------|-------------|")

            for attr_name in sorted(all_attr_types.keys()):
                types = all_attr_types[attr_name]
                type_str = " or ".join(sorted(types))
                output.append(f"| `{attr_name}` | {type_str} | |")

            output.append("")

        # Document relationships
        if all_relationships:
            output.append("### Relationships")
            output.append("")
            for rel_name in sorted(all_relationships):
                output.append(f"- `{rel_name}`")
            output.append("")

        # Add example response
        if example_data:
            output.append("### Example Response")
            output.append("")
            output.append("```json")

            # Show a simplified example (first item if array, limit depth)
            if isinstance(example_data, dict) and "data" in example_data:
                example = {"data": example_data["data"]}
                if isinstance(example["data"], list) and example["data"]:
                    # Show only first item for arrays
                    example["data"] = [example["data"][0]]

                output.append(json.dumps(example, indent=2))
            else:
                output.append(json.dumps(example_data, indent=2))

            output.append("```")
            output.append("")

        output.append("---")
        output.append("")

    # Write documentation to file
    doc_file = Path("API_DOCUMENTATION.md")
    with open(doc_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output))

    print(f"✅ Generated API documentation: {doc_file}")
    print(f"   Documented {len(endpoints)} unique endpoints")


def main():
    """Main entry point"""
    print("=== Generating API Documentation ===\n")
    generate_documentation()


if __name__ == "__main__":
    main()
