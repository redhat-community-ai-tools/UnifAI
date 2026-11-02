"""
Admin Config Template definition.

This is the single source of truth for what appears on the admin
configuration page.  Add new categories / sections / fields here;
the UI renders them dynamically.

Each section's `on_update_action` is an identifier that downstream
services can use to react when values change (e.g. RAG can watch
for "clean_restricted_slack_channels").
"""
from admin_config.models import (
    AdminConfigTemplate,
    CategoryDefinition,
    FieldDefinition,
    SectionDefinition,
)
from config.app_config import AppConfig

config = AppConfig.get_instance()

ADMIN_CONFIG_TEMPLATE = AdminConfigTemplate(
    categories=[
               # ── User Management ─────────────────────────────────────────────
        CategoryDefinition(
            key="user_management",
            title="User Management",
            description="Control who has access to the admin configuration page.",
            sections=[
                SectionDefinition(
                    key="admin_users",
                    title="Admin Users",
                    description=(
                        "SSO usernames of users allowed to access and "
                        "modify admin settings. At least one admin must "
                        "always be present."
                    ),
                    fields=[
                        FieldDefinition(
                            key="admin_usernames",
                            label="Admin Usernames",
                            field_type="string_list",
                            description="SSO usernames (preferred_username) with admin access.",
                            default=config.admin_allowed_users,
                            placeholder="e.g. jdoe",
                        ),
                    ],
                ),
            ],
        ),
        # ── OpenAI Models ───────────────────────────────────────────────────
        CategoryDefinition(
            key="openai_models",
            title="OpenAI Models",
            description=(
                "Configure capabilities for OpenAI Responses API models "
                "(GPT-5+, o-series). Adjust the reasoning-effort levels "
                "available for each model without redeploying."
            ),
            sections=[
                SectionDefinition(
                    key="openai_model_capabilities",
                    title="Model Capabilities",
                    description=(
                        "A JSON dictionary mapping model-name prefixes to their "
                        "supported reasoning levels. "
                        "Keys are matched by prefix — 'gpt-5' matches "
                        "'gpt-5', 'gpt-5.6-sol', etc.  "
                        "More specific prefixes take precedence.\n\n"
                        "Structure:\n"
                        '{"<model-prefix>": {'
                        '"reasoning": ["none","low","medium","high","xhigh","max"]'
                        "}}"
                    ),
                    on_update_action="reload_openai_model_capabilities",
                    fields=[
                        FieldDefinition(
                            key="capabilities",
                            label="Model Capabilities",
                            field_type="json",
                            description=(
                                "Edit the full capabilities map. Changes take effect "
                                "immediately for newly-created sessions."
                            ),
                            default={
                                "gpt-5.6-sol": {
                                    "reasoning": ["none", "low", "medium", "high", "xhigh", "max"],
                                },
                                "gpt-5.6-terra": {
                                    "reasoning": ["none", "low", "medium", "high", "xhigh", "max"],
                                },
                                "gpt-5.6-luna": {
                                    "reasoning": ["none", "low", "medium", "high", "xhigh", "max"],
                                },
                                "gpt-5.5": {
                                    "reasoning": ["none", "low", "medium", "high", "xhigh"],
                                },
                                "gpt-5.2": {
                                    "reasoning": ["none", "low", "medium", "high", "xhigh"],
                                },
                                "gpt-5": {
                                    "reasoning": ["minimal", "low", "medium", "high"],
                                },
                               
                            },
                        ),
                    ],
                ),
            ],
        ),
        # ── Data Source Rules (disabled until backend is fully deployed) ──
        # CategoryDefinition(
        #     key="restricted_channels_rules",
        #     title="Restricted Slack channels Rules",
        #     description="Rules that control which data sources are ingested.",
        #     sections=[
        #         SectionDefinition(
        #             key="slack_channel_restrictions",
        #             title="Slack Channel Restrictions",
        #             description=(
        #                 "Define prefixes, suffixes, and keywords that cause "
        #                 "Slack channels to be excluded from ingestion."
        #             ),
        #             on_update_action="clean_restricted_slack_channels",
        #             on_update_target="rag",
        #             on_update_endpoint="/api/slack/clean-restricted-channels",
        #             fields=[
        #                 FieldDefinition(
        #                     key="restricted_prefixes",
        #                     label="Restricted Prefixes",
        #                     field_type="string_list",
        #                     description="Channels whose name starts with any of these are excluded.",
        #                     default=[
        #                         "erg-",
        #                         "event-",
        #                         "events-",
        #                         "hr-",
        #                         "people-",
        #                         "confidential-",
        #                     ],
        #                     placeholder="e.g. hr-",
        #                 ),
        #                 FieldDefinition(
        #                     key="restricted_suffixes",
        #                     label="Restricted Suffixes",
        #                     field_type="string_list",
        #                     description="Channels whose name ends with any of these are excluded.",
        #                     default=[
        #                         "-erg",
        #                         "-event",
        #                         "-events",
        #                         "-hr",
        #                         "-confidential",
        #                     ],
        #                     placeholder="e.g. -hr",
        #                 ),
        #                 FieldDefinition(
        #                     key="restricted_keywords",
        #                     label="Restricted Keywords",
        #                     field_type="string_list",
        #                     description="Channels whose name contains any of these are excluded.",
        #                     default=[
        #                         "human-resources",
        #                         "employee-relations",
        #                         "performance-review",
        #                     ],
        #                     placeholder="e.g. performance-review",
        #                 ),
        #             ],
        #         ),
        #     ],
        # ),
 
    ],
)
