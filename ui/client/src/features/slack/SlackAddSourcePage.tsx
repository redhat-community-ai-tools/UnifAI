import React, { useRef, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSubmitSlackChannels, ChannelWithSettings } from '@/api/slack';
import AddSourceSection, { AddSourceSectionHandle } from './AddSourceSection';
import Sidebar from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import StatusBar from '@/components/layout/StatusBar';
import { motion } from 'framer-motion';
import { useLocation } from 'wouter';
import { XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { SlackSetupInfo } from './SlackSetupInfo';

export default function SlackAddSourcePage() {
    const [, navigate] = useLocation();
    const queryClient = useQueryClient();
    const { toast } = useToast();
    const submitSlackChannels = useSubmitSlackChannels();

    const {
        mutate: addChannels,
        isPending: isSubmitting,
        isError,
        error,
    } = useMutation({
        mutationFn: submitSlackChannels,
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['slackChannels'] });
            queryClient.invalidateQueries({ queryKey: ['embeddedSlackChannels'] });
            queryClient.invalidateQueries({ queryKey: ['embeddedSlackChannelsStats'] });
            
            // Surface any backend validation issues (e.g., app not installed in channel)
            const issues = (data as any)?.registration?.issues || [];
            const hasIssues = Array.isArray(issues) && issues.length > 0;
            if (hasIssues) {
                issues.forEach((issue: any) => {
                    const issueType = String(issue?.issue_type || "Validation issue");
                    const message = String(issue?.message || "");
                    const isBotNotInstalled = issueType === "Channel bot not installed";
                    toast({
                        title: isBotNotInstalled ? (
                            <span className="inline-flex items-center gap-2">
                                <XCircle className="h-4 w-4 text-red-600" />
                                <span>{issueType}</span>
                            </span>
                        ) : issueType,
                        description: message,
                        variant: "destructive",
                    });
                });
            } else {
                // Only show success toast if there are no blocking issues
                toast({
                    title: "🚀 Embedding Task Started",
                    description: "Your Slack channels have been submitted for processing. You'll see them appear in the integration dashboard as they're processed.",
                    variant: "default",
                });
            }
            
            const channelIds = variables.map(channel => channel.channel_id);
            const channelIdsParam = encodeURIComponent(JSON.stringify(channelIds));
            
            navigate(`/slack?newChannels=${channelIdsParam}`);
        },
        onError: (err: Error) => {
            toast({
                title: (
                    <span className="inline-flex items-center gap-2">
                        <XCircle className="h-4 w-4 text-red-600" />
                        <span>Submission Failed</span>
                    </span>
                ),
                description: `Unable to start embedding process: ${err.message}`,
                variant: "destructive",
            });
        },
    });

    const sectionRef = useRef<AddSourceSectionHandle>(null);

    const handleSave = useCallback(async () => {
        const payload: ChannelWithSettings[] = await sectionRef.current?.getSelectedChannels() ?? [];
        if (payload.length === 0) {
            toast({
                title: "⚠️ No Channels Selected",
                description: "Please select at least one channel to proceed with embedding.",
                variant: "destructive",
            });
            return;
        }
        addChannels(payload);
    }, [addChannels, toast]);

    return (
        <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex-1 flex flex-col overflow-hidden">
                <Header
                    title="Slack Integration – Add Source"
                    onToggleSidebar={() => { }}
                />
                <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                    >
                        <SlackSetupInfo />
                        <div className="mt-6">
                            <AddSourceSection 
                                ref={sectionRef} 
                                onSave={handleSave}
                                onCancel={() => window.history.back()}
                                isSubmitting={isSubmitting}
                            />
                        </div>

                        {isError && (
                            <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive">
                                Error: {error?.message}
                            </div>
                        )}
                    </motion.div>
                </main>
                <StatusBar />
            </div>
        </div>
    );
}
