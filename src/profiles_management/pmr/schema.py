"""This module contains the schema to validate a PMR against."""

PMR_SCHEMA = {
    "type": "object",
    "properties": {
        "profiles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "owner": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["User", "Group", "ServiceAccount"],
                            },
                            "name": {"type": "string"},
                        },
                        "required": ["kind", "name"],
                    },
                    "resources": {
                        "type": "object",
                        # allow arbitrary fields
                        "additionalProperties": True,
                    },
                    "contributors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {
                                    "type": "string",
                                    "enum": ["admin", "edit", "view"],
                                },
                            },
                            "required": ["name", "role"],
                        },
                    },
                },
                # resources are not required in a Profile
                "required": ["name", "owner", "contributors"],
            },
        }
    },
    "required": ["profiles"],
}
