from typing import List
from elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from .utils import ensure_tool_call_id


class LangChainConverter:
    """
    Translates between ChatMessage and LangChain messages.
    """

    @staticmethod
    def to_lc(history: List[ChatMessage]) -> List:
        out = []
        for m in history:
            if m.role == Role.SYSTEM:
                out.append(SystemMessage(content=m.content))

            elif m.role == Role.USER:
                out.append(HumanMessage(content=m.content))

            elif m.role == Role.ASSISTANT:
                if m.tool_calls:
                    tool_calls = [{
                        "name": tc.name,
                        "args": tc.args,
                        "id": tc.tool_call_id,
                        "type": "tool_call"
                    } for tc in m.tool_calls]
                    out.append(AIMessage(
                        content=m.content if m.content else "[TOOL CALL]",
                        tool_calls=tool_calls,
                        additional_kwargs=m.additional_kwargs or {}
                    ))
                else:
                    out.append(AIMessage(content=m.content))

            elif m.role == Role.TOOL:
                # LangChain ToolMessage requires name parameter
                tool_name = getattr(m, 'name', None) or 'unknown_tool'
                out.append(ToolMessage(content=m.content, tool_call_id=m.tool_call_id, name=tool_name))

            else:
                raise ValueError(f"Unknown role {m.role}")
        return out

    @staticmethod
    def from_lc_message(m) -> ChatMessage:
        if isinstance(m, SystemMessage):
            return ChatMessage(role=Role.SYSTEM, content=m.content)

        elif isinstance(m, HumanMessage):
            return ChatMessage(role=Role.USER, content=m.content)

        elif isinstance(m, AIMessage):
            # -------- tool-call reconstruction ------------------------
            tool_calls = None

            #  build them from tool_call_chunks
            if getattr(m, "tool_call_chunks", None) and m.type == "tool_call_chunk":
                tool_calls = [ensure_tool_call_id(tc) for tc in m.tool_call_chunks]

            # Otherwise, provider already supplied complete tool_calls
            elif getattr(m, "tool_calls", None):
                tool_calls = [ensure_tool_call_id(tc) for tc in m.tool_calls]

            return ChatMessage(
                role=Role.ASSISTANT,
                content=m.content or " " if tool_calls else m.content,
                tool_calls=[ToolCall(**tc.to_dict()) for tc in tool_calls] if tool_calls else None,
                additional_kwargs=getattr(m, 'additional_kwargs', None)
            )

        elif isinstance(m, ToolMessage):
            return ChatMessage(role=Role.TOOL,
                               content=m.content,
                               tool_call_id=m.tool_call_id)

        else:
            raise ValueError(f"Unknown message type: {type(m)}")

    @staticmethod
    def from_lc(lc_msgs: List) -> List[ChatMessage]:
        return [LangChainConverter.from_lc_message(m) for m in lc_msgs]
