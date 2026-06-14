import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createToken, listTokens, revokeToken, type ApiToken } from "@/api/tokens";
import { Copy, Key, Trash2, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function UserManagement() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showRevokeDialog, setShowRevokeDialog] = useState<string | null>(null);
  const [tokenName, setTokenName] = useState("");
  const [newToken, setNewToken] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: tokens = [], isLoading } = useQuery({
    queryKey: ["api-tokens"],
    queryFn: listTokens,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => createToken(name),
    onSuccess: (data) => {
      setNewToken(data.token);
      setTokenName("");
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (name: string) => revokeToken(name),
    onSuccess: () => {
      setShowRevokeDialog(null);
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
      toast({ title: "Token revoked", description: "The token has been permanently revoked." });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const handleCreate = () => {
    if (!tokenName.trim()) return;
    createMutation.mutate(tokenName.trim());
  };

  const handleCopy = () => {
    if (newToken) {
      navigator.clipboard.writeText(newToken);
      toast({ title: "Copied", description: "Token copied to clipboard." });
    }
  };

  const handleCloseCreate = () => {
    setShowCreateDialog(false);
    setNewToken(null);
    setTokenName("");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#0D1117]">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            <div>
              <h1 className="text-2xl font-bold text-white">User Management</h1>
              <p className="text-gray-400 mt-1">Manage your account and API access.</p>
            </div>

            <Card className="bg-[#161B22] border-gray-800">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Key className="h-5 w-5" />
                    API Tokens
                  </CardTitle>
                  <CardDescription className="text-gray-400">
                    Create tokens for programmatic API access. Tokens expire after 90 days.
                  </CardDescription>
                </div>
                <Button
                  onClick={() => setShowCreateDialog(true)}
                  className="bg-primary hover:bg-primary/80"
                >
                  Create Token
                </Button>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="text-gray-400 text-sm">Loading tokens...</div>
                ) : tokens.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Key className="h-10 w-10 mx-auto mb-3 opacity-50" />
                    <p>No API tokens yet.</p>
                    <p className="text-sm mt-1">Create a token to access the UnifAI API programmatically.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {tokens.map((token: ApiToken) => (
                      <div
                        key={token.name}
                        className="flex items-center justify-between p-3 rounded-lg bg-[#0D1117] border border-gray-800"
                      >
                        <div className="flex-1">
                          <div className="font-medium text-white">{token.name}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            Created {new Date(token.created_at).toLocaleDateString()} ·
                            Expires {new Date(token.expires_at).toLocaleDateString()}
                            {token.last_used_at && (
                              <> · Last used {new Date(token.last_used_at).toLocaleDateString()}</>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowRevokeDialog(token.name)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-900/20"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
        <StatusBar />
      </div>

      {/* Create Token Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={handleCloseCreate}>
        <DialogContent className="bg-[#161B22] border-gray-800 text-white">
          <DialogHeader>
            <DialogTitle>{newToken ? "Token Created" : "Create API Token"}</DialogTitle>
            <DialogDescription className="text-gray-400">
              {newToken
                ? "Copy your token now. You won't be able to see it again."
                : "Give your token a name to identify its purpose."}
            </DialogDescription>
          </DialogHeader>

          {!newToken ? (
            <>
              <div className="space-y-4 py-4">
                <input
                  type="text"
                  placeholder="Token name (e.g., ci-pipeline)"
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  className="flex h-10 w-full rounded-md border px-3 py-2 text-sm"
                  style={{ backgroundColor: "#1c2128", color: "#ffffff", borderColor: "#444c56" }}
                />
              </div>
              <DialogFooter>
                <Button variant="ghost" onClick={handleCloseCreate}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={!tokenName.trim() || createMutation.isPending}
                  className="bg-primary hover:bg-primary/80"
                >
                  {createMutation.isPending ? "Creating..." : "Create"}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <div className="space-y-4 py-4">
                <div className="flex items-center gap-2 p-3 rounded-lg bg-[#0D1117] border border-gray-700">
                  <code className="flex-1 text-xs text-green-400 break-all font-mono">
                    {newToken}
                  </code>
                  <Button variant="ghost" size="sm" onClick={handleCopy}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex items-start gap-2 text-amber-400 text-sm">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <span>Save this token — it cannot be retrieved again.</span>
                </div>
              </div>
              <DialogFooter>
                <Button onClick={handleCloseCreate} className="bg-primary hover:bg-primary/80">
                  Done
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Revoke Confirmation Dialog */}
      <Dialog open={!!showRevokeDialog} onOpenChange={() => setShowRevokeDialog(null)}>
        <DialogContent className="bg-[#161B22] border-gray-800 text-white">
          <DialogHeader>
            <DialogTitle>Revoke Token</DialogTitle>
            <DialogDescription className="text-gray-400">
              Are you sure you want to revoke <strong className="text-white">{showRevokeDialog}</strong>?
              This action cannot be undone. Any scripts using this token will stop working.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowRevokeDialog(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => showRevokeDialog && revokeMutation.mutate(showRevokeDialog)}
              disabled={revokeMutation.isPending}
            >
              {revokeMutation.isPending ? "Revoking..." : "Revoke"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
