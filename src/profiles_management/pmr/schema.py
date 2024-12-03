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
                        "additionalProperties": False,
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["User", "Group", "ServiceAccount"],
                            },
                            "name": {"type": "string"},
                        },
                        "required": ["kind", "name"],
                    },
                    # https://kubernetes.io/docs/reference/kubernetes-api/policy-resources/resource-quota-v1/#ResourceQuotaSpec
                    "resources": {
                        "type": "object",
                        "additionalProperties": False,
                        "anyOf": [
                            # Either hard is required, or no keys at all
                            {"required": ["hard"]},
                            {"maxProperties": 0},
                        ],
                        "properties": {
                            "hard": {
                                "type": "object",
                                # allow arbitrary fields
                                "additionalProperties": True,
                            },
                            "scopeSelector": {
                                "type": "object",
                                "properties": {
                                    "matchExpressions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["operator", "scopeName"],
                                            "properties": {
                                                "operator": {
                                                    "type": "string",
                                                    "enum": [
                                                        "In",
                                                        "NotIn",
                                                        "Exists",
                                                        "DoesNotExist",
                                                    ],
                                                },
                                                "scopeName": {
                                                    "type": "string",
                                                },
                                                "values": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            "scopes": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                    },
                    "contributors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
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
