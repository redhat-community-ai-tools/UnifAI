import axios from "@/http/axiosAgentConfig";

export const joinSession = async (
  sessionId: string,
  role = "collaborator",
) => {
  return axios.post("/collaboration/session.join", {
    sessionId,
    role,
  });
};

export const leaveSession = async (
  sessionId: string,
) => {
  return axios.post("/collaboration/session.leave", { sessionId });
};

export const sendHeartbeat = async (
  sessionId: string,
) => {
  return axios.post("/collaboration/session.heartbeat", { sessionId });
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
  isTyping: boolean,
) => {
  return axios.post("/collaboration/session.typing", {
    sessionId,
    isTyping,
  });
};
