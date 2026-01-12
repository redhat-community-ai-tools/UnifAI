export enum UmamiEvents {
    // buttons' event names
    AGENT_CHAT_TOGGLE_EXECUTION_STREAM_BUTTON = "agent-chat-toggle-execution-stream-button",
    AGENT_CHAT_TOGGLE_GLOBAL_SCOPE_BUTTON = "agent-chat-toggle-global-scope-button",
    AGENT_CHAT_ADD_FLOW_BUTTON = "agent-chat-add-flow-button",
    AGENT_CHAT_DELETE_CHAT_BUTTON = "agent-chat-delete-chat-button",
    AGENT_CHAT_SEND_MESSAGE_BUTTON = "agent-chat-send-message-button",
    AGENT_GRAPHS_BACK_BUTTON = "agent-graphs-back-button",
    AGENT_GRAPHS_CLEAR_BUTTON = "agent-graphs-clear-button",
    AGENT_GRAPHS_SAVE_BUTTON = "agent-graphs-save-blueprint-button",
    AGENT_GRAPHS_LOAD_FLOW_BUTTON = "agent-graphs-load-flow-button",
    AGENT_GRAPHS_BUILD_FLOW_BUTTON = "agent-graphs-build-flow-button",
    AGENT_GRAPHS_CONDITIONS_BUTTON = "agent-graphs-conditions-button",
    AGENT_REPOSITORY_SAVE_ELEMENT_BUTTON = "agent-repository-save-element-button",
    AGENT_REPOSITORY_CREATE_NEW_BUTTON = "agent-repository-create-new-button",
    WORKFLOW_SHARE_COPY_LINK = "workflow-share-copy-link",
    PUBLIC_CHAT_NEW_SESSION = "public-chat-new-session",
    SHARED_SYSTEM_BUTTON = "shared-system-button",
    NOTIFICATIONS_BUTTON = "notifications-button",
    UPLOAD_DOCUMENT_BUTTON = "upload-document-button",
    VIEW_DOCUMENT_LIST_BUTTON = "view-document-list-button",
    VIEW_DOCUMENT_GRID_BUTTON = "view-document-grid-button",
    SLACK_DELETE_SOURCE_BUTTON = "slack-deletesource-button",
    SLACK_ADD_SOURCE_BUTTON = "slack-addsource-button"
}

export type UmamiEventData = {
    userId?: string;
    channelName?: string;
    flowName?: string;
    elementType?: string;
    [key: string]: string | number | boolean | undefined;
}
