import { Route, Switch, useLocation } from "wouter";
import RagOverview from "@/pages/RagOverview";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import JiraIntegration from "@/pages/JiraIntegration";
import AgenticWorkflows from "@/pages/AgenticWorkflows";
import AgentRepository from "@/pages/AgentRepository";
import AgenticChats from "@/pages/AgenticChats";
import GetToKnow from "@/pages/GetToKnow";
import NotFound from "@/pages/not-found";
import { useEffect } from "react";
import { ProjectProvider } from '@/contexts/ProjectContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SharedProvider } from '@/contexts/SharedContext';
import DocumentsPage from "./features/docs/DocumentsPage";
import { AuthProvider } from '@/contexts/AuthContext';
import { AgenticAIProvider } from '@/contexts/AgenticAIContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import TermsApproval from '@/components/auth/TermsApproval';
import SlackIntegration from "./features/slack/SlackIntegration";
import SlackAddSourcePage from "./features/slack/SlackAddSourcePage";
import GuidesPage from "./components/guides/GuidesPage";
import PublicChat from "./components/agentic-ai/chat/PublicChat";

// Paths that require AgenticAIProvider
const AGENTIC_PATHS = ['/agentic-overview', '/agentic-ai', '/inventory', '/agentic-chats'];

// Routes component that conditionally wraps agentic routes with the shared provider
function AppRoutes() {
  const [location] = useLocation();
  
  const isAgenticRoute = AGENTIC_PATHS.some(path => location === path);

  if (isAgenticRoute) {
    return (
      <AgenticAIProvider>
        <Switch>
          <Route path="/agentic-overview" component={AgenticOverview} />
          <Route path="/agentic-ai" component={AgenticWorkflows} />
          <Route path="/inventory" component={AgentRepository} />
          <Route path="/agentic-chats" component={AgenticChats} />
        </Switch>
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
      <Route path="/chat/:token" component={PublicChat} />
      <Route component={NotFound} />
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
          <ProjectProvider>
            <NotificationProvider>
              <ProtectedRoute>
                <TermsApproval>
                  <AppRoutes />
                </TermsApproval>
              </ProtectedRoute>
            </NotificationProvider>
          </ProjectProvider>
        </SharedProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
              
