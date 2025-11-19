import { GraphFlow } from '../interfaces'

// Example graph flow from your JSON
export const latestExampleGraphFlow: { [id: string]: GraphFlow }[] = [
  {
    "6da23f69-4bbe-467a-af08-bb3a53a8bd1d": {
      "conditions": [],
      "description": "This Blueprint defines a multi-agent system that integrates two agents:\n- A Document Retrieval Assistant that answers questions based on document excerpts.\n- A Slack Context Assistant that answers questions based on Slack messages.\nThe responses from both agents are merged into a final answer.\n",
      "display_description": "A pipeline that searches through docs and Slack messages to answer user queries\n",
      "display_name": "Document & Slack Search\n",
      "llms": [
        {
          "_meta": {
            "category": "llm",
            "description": "Official OpenAI API configuration",
            "display_name": "OpenAI",
            "type": "openai"
          },
          "api_key": "EMPTY",
          "base_url": "http://localhost:8000/v1",
          "extra": {},
          "max_tokens": 4096,
          "model_name": "Qwen/Qwen2.5-7B-Instruct",
          "name": "openai_llm",
          "temperature": 0.7,
          "type": "openai"
        }
      ],
      "plan": [
        {
          "after": null,
          "branches": null,
          "exit_condition": null,
          "name": "user_input",
          "node": {
            "_meta": {
              "category": "node",
              "description": "Captures and forwards the user\u2019s question",
              "display_name": "User Question Node",
              "type": "user_question_node"
            },
            "llm": null,
            "meta": null,
            "name": null,
            "retries": 1,
            "retriever": null,
            "system_message": null,
            "tools": [],
            "type": "user_question_node"
          }
        },
        {
          "after": "user_input",
          "branches": null,
          "exit_condition": null,
          "name": "docs_agent",
          "node": {
            "_meta": {
              "category": "node",
              "description": "Agent node with LLM, retriever, tools, and prompt overrides",
              "display_name": "Custom Agent Node",
              "type": "custom_agent_node"
            },
            "llm": "openai_llm",
            "meta": {
              "description": "Retrieve doc data\n",
              "display_name": "Doc Agent",
              "tags": []
            },
            "name": "docs_agent_node",
            "retries": 1,
            "retriever": "my_docs",
            "system_message": "You are a Document Retrieval Assistant.\n\u2022 Use only the excerpts returned from the docs retriever as your context.\n\u2022 Answer the user\u2019s question strictly from those document passages.\n\u2022 If you quote or paraphrase, include the source document name in brackets.\n\u2022 mention all the documents names you take the info from.\n\u2022 If no document passage is relevant, respond: \u201cI\u2019m sorry, I don\u2019t know.\u201d\n",
            "tools": [],
            "type": "custom_agent_node"
          }
        },
        {
          "after": "user_input",
          "branches": null,
          "exit_condition": null,
          "name": "slack_agent",
          "node": {
            "_meta": {
              "category": "node",
              "description": "Agent node with LLM, retriever, tools, and prompt overrides",
              "display_name": "Custom Agent Node",
              "type": "custom_agent_node"
            },
            "llm": "openai_llm",
            "meta": {
              "description": "Retrieve slack data\n",
              "display_name": "Slack Agent",
              "tags": []
            },
            "name": "slack_agent_node",
            "retries": 1,
            "retriever": "my_slack",
            "system_message": "You are a Slack Context Assistant.\n\u2022 Use only the messages returned from the Slack retriever as your context.\n\u2022 Answer the user\u2019s question strictly based on those Slack messages.\n\u2022 If you refer to a specific message, indicate the timestamp or author.\n\u2022 If no Slack message is relevant, respond: \u201cI\u2019m sorry, I don\u2019t know.\u201d\n",
            "tools": [],
            "type": "custom_agent_node"
          }
        },
        {
          "after": [
            "docs_agent",
            "slack_agent"
          ],
          "branches": null,
          "exit_condition": null,
          "name": "agent_merger",
          "node": {
            "_meta": {
              "category": "node",
              "description": "Aggregates and synthesizes agent outputs",
              "display_name": "Merger Node",
              "type": "merger_node"
            },
            "llm": "openai_llm",
            "meta": null,
            "name": "agent_merger_node",
            "retries": 1,
            "retriever": null,
            "system_message": "You are a Multi-Source Synthesis Assistant.\n\u2022 You have two inputs: the \u201cDocs Assistant\u201d answer and the \u201cSlack Assistant\u201d answer.\n\u2022 Combine them into one concise, coherent response.\n\u2022 If they agree, merge seamlessly; if they conflict, note the discrepancy.\n\u2022 If both say \u201cI\u2019m sorry, I don\u2019t know,\u201d respond: \u201cI\u2019m sorry, I don\u2019t know.\u201d\n",
            "tools": [],
            "type": "merger_node"
          }
        },
        {
          "after": "agent_merger",
          "branches": null,
          "exit_condition": null,
          "name": "finalize",
          "node": {
            "_meta": {
              "category": "node",
              "description": "Outputs the final response",
              "display_name": "Final Answer Node",
              "type": "final_answer_node"
            },
            "llm": null,
            "meta": null,
            "name": null,
            "retries": 1,
            "retriever": null,
            "system_message": null,
            "tools": [],
            "type": "final_answer_node"
          }
        }
      ],
      "retrievers": [
        {
          "_meta": {
            "category": "retriever",
            "description": "Fetches relevant document passages for a query",
            "display_name": "Docs Retriever",
            "type": "docs"
          },
          "api_url": "http://0.0.0.0:13456/api/docs/query.match",
          "name": "my_docs",
          "threshold": 0.3,
          "top_k_results": 5,
          "type": "docs"
        },
        {
          "_meta": {
            "category": "retriever",
            "description": "Fetches recent messages matching a query from Slack",
            "display_name": "Slack Retriever",
            "type": "slack"
          },
          "api_url": "http://0.0.0.0:13456/api/slack/query.match",
          "name": "my_slack",
          "threshold": 0.3,
          "top_k_results": 3,
          "type": "slack"
        }
      ],
      "tools": []
    }
  }
]