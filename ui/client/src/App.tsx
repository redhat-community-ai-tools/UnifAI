import React, { useEffect } from "react";
import { Route, Switch, useRoute } from "wouter";
import RagOverview from "@/pages/RagOverview";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import JiraIntegration from "@/pages/JiraIntegration";
import AgenticWorkflows from "@/pages/AgenticWorkflows";
import AgentRepository from "@/pages/AgentRepository";
import AgenticChats from "@/pages/AgenticChats";

import AgenticTemplates from "@/pages/AgenticTemplates";
import GetToKnow from "@/pages/GetToKnow";
import Analytics from "@/pages/Analytics";
import NotFound from "@/pages/not-found";
import Login from "@/pages/Login";
import { ProjectProvider } from '@/contexts/ProjectContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SharedProvider } from '@/contexts/SharedContext';
import { ViewProvider, useView } from '@/contexts/ViewContext';
import DocumentsPage from "./features/docs/DocumentsPage";
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AgenticAIProvider } from '@/contexts/AgenticAIContext';
import { useTheme } from '@/contexts/ThemeContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import TermsApproval from '@/components/auth/TermsApproval';
import SlackIntegration from "./features/slack/SlackIntegration";
import SlackAddSourcePage from "./features/slack/SlackAddSourcePage";
import GuidesPage from "./components/guides/GuidesPage";
import PublicChat from "./components/agentic-ai/chat/PublicChat";
import AgenticLayout from "./components/layout/AgenticLayout";
import { Toaster } from "./components/ui/toaster";

function AppRoutes() {
  const { viewMode } = useView();
  const [isChat] = useRoute("/chat/:token");
  const [isAgenticOverview] = useRoute("/agentic-overview");
  const [isAgenticAI] = useRoute("/agentic-ai");
  const [isInventory] = useRoute("/inventory");
  const [isAgenticChats] = useRoute("/agentic-chats");
  const [isTemplates] = useRoute("/templates");
  const [isRagOverview] = useRoute("/rag-overview");
  const [isSlack] = useRoute("/slack");
  const [isDocuments] = useRoute("/documents");
  const [isSlackAddSource] = useRoute("/slack/add-source");

  const isAgenticRoute = isAgenticOverview || isAgenticAI || isInventory || isAgenticChats || isTemplates;
  const isTeamBlockedRagRoute =
    viewMode === "team" &&
    (isRagOverview || isSlack || isDocuments || isSlackAddSource);

  if (isChat) {
    return (
      <AgenticAIProvider>
        <Route path="/chat/:token" component={PublicChat} />
      </AgenticAIProvider>
    );
  }

  if (isAgenticRoute || isTeamBlockedRagRoute) {
    return (
      <AgenticAIProvider>
        <AgenticLayout>
          <Switch>
            <Route path="/agentic-overview" component={AgenticOverview} />
            <Route path="/agentic-ai" component={AgenticWorkflows} />
            <Route path="/inventory" component={AgentRepository} />
            <Route path="/agentic-chats" component={AgenticChats} />
            <Route path="/templates" component={AgenticTemplates} />
          </Switch>
        </AgenticLayout>
      </AgenticAIProvider>
    );
  }


  return (
    <Switch>
      <Route path="/" component={GetToKnow} />
      <Route path="/rag-overview" component={RagOverview} />
      <Route path="/jira" component={JiraIntegration} />
      <Route path="/slack" component={SlackIntegration} />
      <Route path="/documents" component={DocumentsPage} />
      <Route path="/slack/add-source" component={SlackAddSourcePage} />
      <Route path="/get-to-know" component={GetToKnow} />
      <Route path="/configuration" component={Configuration} />
      <Route path="/guides" component={GuidesPage} />
      <Route path="/analytics" component={Analytics} />
      <Route component={NotFound} />
    </Switch>
  );
}

/** /login outside ProtectedRoute; use full navigation (no wouter setLocation) to match app routing convention. */
function LoginRouteContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const { primaryHex } = useTheme();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      window.location.replace('/');
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0D1117]">
        <div
          className="animate-spin rounded-full h-12 w-12 border-b-2"
          style={{ borderBottomColor: primaryHex || "#A60000" }}
        />
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  return <Login />;
}

function AppContent() {
  return (
    <Switch>
      <Route path="/login">
        <LoginRouteContent />
      </Route>
      <Route>
        <ProtectedRoute>
          <TermsApproval>
            <AppRoutes />
          </TermsApproval>
        </ProtectedRoute>
      </Route>
    </Switch>
  );
}

function App() {
  // Set document title
  useEffect(() => {
    document.title = "UnifAI";
  }, []);

  return (
    <ThemeProvider>
      <AuthProvider>
        <SharedProvider>
          <ViewProvider>
            <ProjectProvider>
              <NotificationProvider>
                <AppContent />
              </NotificationProvider>
            </ProjectProvider>
          </ViewProvider>
        </SharedProvider>
      </AuthProvider>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;

