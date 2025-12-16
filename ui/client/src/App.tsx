import { Route, Switch } from "wouter";
import RagOverview from "@/pages/RagOverview";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import JiraIntegration from "@/pages/JiraIntegration";
import AgenticAI from "@/pages/AgenticAI";
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
import SlackIntegration from "./features/slack/SlackIntegration";
import SlackAddSourcePage from "./features/slack/SlackAddSourcePage";
import GuidesPage from "./components/guides/GuidesPage";

const withAgenticAIProvider = <P extends object>(Component: React.ComponentType<P>) => {
  return (props: P) => (
    <AgenticAIProvider>
      <Component {...props} />
    </AgenticAIProvider>
  );
};

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
                <Switch>
                  {/* Agentic AI routes - wrapped with AgenticAIProvider */}
                  <Route path="/" component={GetToKnow} />
                  <Route path="/agentic-overview" component={withAgenticAIProvider(AgenticOverview)} />
                  <Route path="/agentic-ai" component={withAgenticAIProvider(AgenticAI)} />
                  <Route path="/inventory" component={withAgenticAIProvider(AgentRepository)} />
                  <Route path="/agentic-chats" component={withAgenticAIProvider(AgenticChats)} />
                  
                  {/* Non-agentic routes - don't need AgenticAIProvider */}
                  <Route path="/rag-overview" component={RagOverview} />
                  <Route path="/jira" component={JiraIntegration} />
                  <Route path="/slack" component={SlackIntegration} />
                  <Route path="/documents" component={DocumentsPage} />
                  <Route path="/slack/add-source" component={SlackAddSourcePage} />
                  <Route path="/get-to-know" component={GetToKnow} />
                  <Route path="/configuration" component={Configuration} />
                  <Route path="/guides" component={GuidesPage} />
                  <Route component={NotFound} />
                </Switch>
              </ProtectedRoute>
            </NotificationProvider>
          </ProjectProvider>
        </SharedProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
              
