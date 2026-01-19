#!/usr/bin/env python3
"""Test how Pydantic generates JSON schema from Annotated types."""

from typing import Annotated, Optional, get_type_hints, get_args, get_origin
from pydantic import Field, TypeAdapter
from pydantic.fields import FieldInfo
import json


def example_tool(
    max_results: Annotated[
        Optional[int],
        Field(description='Maximum number of events to return (1-50, default: 10)'),
    ] = None,
):
    """Example tool with Annotated parameter."""
    pass


print("=== Type Hints ===")
hints = get_type_hints(example_tool, include_extras=True)
print(f"max_results: {hints['max_results']}")
print()

annotation = hints['max_results']
print("=== Annotation Analysis ===")
print(f"Origin: {get_origin(annotation)}")
print(f"Args: {get_args(annotation)}")
print()

args = get_args(annotation)
field_info = None
for arg in args:
    if isinstance(arg, FieldInfo):
        field_info = arg
        break

print("=== Field Info ===")
if field_info:
    print(f"Description: {field_info.description}")
    print(f"Default: {field_info.default}")
    print(f"Is Required: {field_info.is_required()}")
else:
    print("No FieldInfo found")
print()

print("=== JSON Schema Generation ===")
try:
    actual_type = args[0] if args else annotation
    print(f"Actual type to convert: {actual_type}")

    adapter = TypeAdapter(actual_type)
    schema = adapter.json_schema()
    print("Generated schema:")
    print(json.dumps(schema, indent=2))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
