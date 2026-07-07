import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { useAdminAccess } from "@/hooks/use-admin-access";
import { useAuth } from "@/contexts/AuthContext";
import { AccessDenied } from "@/components/shared/AccessDenied";
import {
  getAdminConfig,
  type AdminConfigResponse,
} from "@/api/adminConfig";
import AdminConfigSection from "@/features/configuration/AdminConfigSection";
import RepositoryManagement from "@/features/configuration/RepositoryManagement";
import { AgenticAIProvider } from "@/contexts/AgenticAIContext";

export default function Configuration() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isAdmin, isLoading: isAdminLoading } = useAdminAccess();

  if (isAdminLoading) {
    return (
      <PageShell sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}>
        <div className="space-y-4">
          <Skeleton className="h-10 w-96" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageShell>
    );
  }

  if (!isAdmin) {
    return (
      <PageShell sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}>
        <AccessDenied />
      </PageShell>
    );
  }

  return (
    <PageShell sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}>
      <AdminConfigTabs />
    </PageShell>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Page shell — shared layout (sidebar, header, status bar)
// ─────────────────────────────────────────────────────────────────────────────

function PageShell({
  children,
  sidebarOpen,
  setSidebarOpen,
}: {
  children: React.ReactNode;
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
}) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Configuration Manager"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          {children}
        </main>
        <StatusBar />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Dynamic tabs — one per backend category
// ─────────────────────────────────────────────────────────────────────────────

function AdminConfigTabs() {
  const { user } = useAuth();
  const {
    data: config,
    isLoading,
    isError,
    error,
  } = useQuery<AdminConfigResponse>({
    queryKey: ["admin_config", user?.username],
    queryFn: () => getAdminConfig(),
    staleTime: 30 * 1000,
    refetchOnMount: true,
  });

  if (isLoading) return <TabsSkeleton />;
  if (isError) return <ErrorState message={(error as Error)?.message} />;
  if (!config || config.categories.length === 0) return null;

  const defaultTab = config.categories[0].key;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Tabs defaultValue={defaultTab} className="w-full">
        <TabsList className="mb-6">
          {config.categories.map((category) => (
            <TabsTrigger
              key={category.key}
              value={category.key}
              className="data-[state=active]:bg-primary data-[state=active]:text-white"
            >
              {category.title}
            </TabsTrigger>
          ))}
          <TabsTrigger
            value="__repository_management__"
            className="data-[state=active]:bg-primary data-[state=active]:text-white"
          >
            Repository Management
          </TabsTrigger>
        </TabsList>

        {config.categories.map((category) => (
          <TabsContent key={category.key} value={category.key}>
            <div className="space-y-8">
              {category.description && (
                <p className="text-sm text-gray-400">
                  {category.description}
                </p>
              )}

              <div className="grid grid-cols-1 gap-6">
                {category.sections.map((section) => (
                  <AdminConfigSection
                    key={section.key}
                    section={section}
                  />
                ))}
              </div>
            </div>
          </TabsContent>
        ))}

        <TabsContent value="__repository_management__">
          <AgenticAIProvider>
            <RepositoryManagement />
          </AgenticAIProvider>
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Loading / Error states
// ─────────────────────────────────────────────────────────────────────────────

function TabsSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-80" />
      {[1, 2].map((i) => (
        <Card
          key={i}
          className="bg-background-card shadow-card border-gray-800"
        >
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-96" />
            <div className="space-y-3 mt-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ErrorState({ message }: { message?: string }) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardContent className="p-6 text-center">
        <p className="text-red-400 font-medium">
          Failed to load configuration
        </p>
        <p className="text-sm text-gray-400 mt-1">
          {message || "Could not connect to the platform backend."}
        </p>
      </CardContent>
    </Card>
  );
}
