import axios from "@/http/axiosAgentConfig";

export const joinSession = async (
  sessionId: string,
  userId: string,
  displayName: string,
  role = "collaborator",
) => {
  return axios.post("/collaboration/session.join", {
    sessionId,
    userId,
    displayName,
    role,
  });
};

export const leaveSession = async (
  sessionId: string,
  userId: string,
) => {
  return axios.post("/collaboration/session.leave", { sessionId, userId });
};

export const sendHeartbeat = async (
  sessionId: string,
  userId: string,
) => {
  return axios.post("/collaboration/session.heartbeat", { sessionId, userId });
};

export const fetchParticipants = async (sessionId: string) => {
  const res = await axios.get(
    `/collaboration/session.participants?sessionId=${sessionId}`,
  );
  return (res.data?.participants || []).map((p: any) => p.user_id) as string[];
};

export const fetchTypingUsers = async (sessionId: string) => {
  const res = await axios.get(
    `/collaboration/session.typing?sessionId=${sessionId}`,
  );
  return (res.data?.typingUsers || []) as string[];
};

export const sendTypingSignal = async (
  sessionId: string,
  userId: string,
  isTyping: boolean,
) => {
  return axios.post("/collaboration/session.typing", {
    sessionId,
    userId,
    isTyping,
  });
};
