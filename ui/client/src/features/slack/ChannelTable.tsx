import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FaSync, FaCog, FaPlus, FaTrash, FaUsers, FaGlobe } from "react-icons/fa";
import { HiOutlineLockClosed } from "react-icons/hi";
import { useLocation } from "wouter";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { EmbedChannel } from "@/types";
import { Badge } from "@/components/ui/badge";
import { DataTable, DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { PIPELINE_STATUS } from "@/constants/pipelineStatus";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { isEmbeddingActivelyProcessing } from "../helpers";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import type { User } from "@/contexts/AuthContext";

export function isChannelNew(createdAt: Date): boolean {
  const now = new Date()
  const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  return createdAt > dayAgo
}

export function getColumns(
  onSettingsClick: (ch: EmbedChannel) => void,
  onDeleteClick: (ch: EmbedChannel) => void,
  deletingChannelId?: string,
  activeEmbeddingIds: string[] = [],
): DataTableColumn<EmbedChannel>[] {

  return [
    {
      accessorKey: "name",
      header: "Channel",
      cell: ({ row }) => {
        const channel = row.original
        const isNew = channel.created && isChannelNew(new Date(channel.created))
        
        return (
          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              {channel.is_private ? (
                <HiOutlineLockClosed className="mr-2 h-4 w-4" />
              ) : (
                <span className="mr-2">#</span>
              )}
              <span className="font-medium text-foreground">
                {channel.name}
              </span>
              {isNew && (
                <Badge className="bg-green-500/20 text-green-400 animate-pulse border-green-400/30">
                  NEW
                </Badge>
              )}
            </div>
            {channel.initialTimestamp && (
              <span className="text-xs text-muted-foreground mt-1 ml-5">
                {channel.initialTimestamp === 'all'
                  ? 'Messages from all time'
                  : `Messages starting from: ${channel.initialTimestamp}`}
              </span>
            )}
          </div>
        )
      }
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: (info) => {
        const channel = info.row.original;
        const isFailed = channel.status === PIPELINE_STATUS.FAILED;
        // Try to extract a failure message if backend provides one
        const failureMessage = channel.type_data?.last_error;
        if (!isFailed) {
          return <StatusBadge status={channel.status} />;
        }

        return (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="inline-flex">
                  <StatusBadge status={channel.status} />
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" align="center" className="max-w-xs">
                <p className="text-sm">
                  {failureMessage || "Embedding failed. Open the channel to view details and retry."}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      },
      filterFn: (row, columnId, filterValue) => {
        const status = row.getValue(columnId) as EmbedChannel["status"];
        let displayLabel: string;
        
        switch (status) {
          case PIPELINE_STATUS.ACTIVE:
            displayLabel = "In Progress";
            break;
          case PIPELINE_STATUS.PAUSED:
            displayLabel = "Paused";
            break;
          case PIPELINE_STATUS.DONE:
            displayLabel = "Done";
            break;
          case PIPELINE_STATUS.FAILED:
            displayLabel = "Failed";
            break;
          case PIPELINE_STATUS.ARCHIVED:
            displayLabel = "Archived";
            break;
          case PIPELINE_STATUS.PENDING:
            displayLabel = "Pending";
            break;
          case PIPELINE_STATUS.CHUNKING_AND_EMBEDDING:
            displayLabel = "Chunking & Embedding";
            break;
          case PIPELINE_STATUS.STORING:
            displayLabel = "Storing";
            break;
          case PIPELINE_STATUS.COLLECTING:
            displayLabel = "Collecting";
            break;
          case PIPELINE_STATUS.PROCESSING:
            displayLabel = "Processing";
            break;
          case PIPELINE_STATUS.ORCHESTRATING:
            displayLabel = "Orchestrating";
            break;
          default:
            displayLabel = status || "Pending";
        }
        
        return displayLabel === filterValue;
      },
      meta: {
        align: "center",
        filterType: "select",
        filterOptions: [
          "Pending",
          "In Progress", 
          "Collecting",
          "Processing",
          "Chunking & Embedding",
          "Storing",
          "Orchestrating",
          "Done",
          "Paused",
          "Failed",
          "Archived"
        ],
      },
    },
    {
      accessorKey: "messages",
      header: "Messages",
      cell: (info) => (
        <span className="text-muted-foreground">{info.getValue<string>()}</span>
      ),
      meta: { align: "left", filterType: "text" },
      filterFn: "includesString",
    },
    {
      accessorKey: "lastSync",
      header: "Last Sync",
      cell: (info) => (
        <span className="text-muted-foreground">{info.getValue<string>()}</span>
      ),
      meta: { align: "left", filterType: "text" },
      filterFn: "includesString",
    },
    {
      accessorKey: "created",
      header: "Created At",
      cell: (info) => (
        <span className="text-muted-foreground">{info.getValue<string>()}</span>
      ),
      sortingFn: (rowA, rowB, columnId) => {
        const dateA = new Date(rowA.getValue(columnId) as string);
        const dateB = new Date(rowB.getValue(columnId) as string);
        
        // Handle invalid dates
        if (isNaN(dateA.getTime()) && isNaN(dateB.getTime())) return 0;
        if (isNaN(dateA.getTime())) return 1;
        if (isNaN(dateB.getTime())) return -1;
        
        return dateA.getTime() - dateB.getTime();
      },
      meta: { align: "left", filterType: "text" },
      filterFn: "includesString",
    },
    {
      accessorKey: "is_private",
      header: () => (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="cursor-help">Channel Privacy</span>
            </TooltipTrigger>
            <TooltipContent>
              <p>Slack channel's built-in privacy setting.<br/>Determines who can see and join the channel.</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ),
      cell: (info) => {
        const isPrivate = info.getValue<boolean>();
        return (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium cursor-help ${
                  isPrivate 
                    ? "bg-amber-500/15 text-amber-400 border border-amber-400/20" 
                    : "bg-blue-500/15 text-blue-400 border border-blue-400/20"
                }`}>
                  {isPrivate ? (
                    <>
                      <HiOutlineLockClosed className="mr-1 h-3 w-3" />
                      Private
                    </>
                  ) : (
                    <>
                      <span className="mr-1">#</span>
                      Public
                    </>
                  )}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p>{isPrivate ? "Private Slack channel - only invited members can see" : "Public Slack channel - visible to all workspace members"}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      },
      filterFn: (row, columnId, filterValue) => {
        const isPrivate = row.getValue(columnId) as boolean;
        const rowValue = isPrivate ? "Private" : "Public";
        return rowValue === filterValue;
      },
      meta: {
        align: "center",
        filterType: "select",
        filterOptions: [
          "Private",
          "Public"
        ],
      },
    },
    {
      accessorKey: "frequency",
      header: "Frequency",
      cell: (info) => (
        <span className="text-muted-foreground">{info.getValue<string>()}</span>
      ),
      meta: { align: "center", filterType: "text" },
      filterFn: "includesString",
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: (info) => {
        const ch = info.row.original;
        const isDeleting = deletingChannelId === ch.channel_id;
        return (
          <div className="flex justify-end space-x-2">
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
              <Button
                variant="ghost"
                size="sm"
                className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-all duration-200"
                onClick={() => {
                  /* optional per-row refresh */
                }}
              >
                <FaSync className="h-4 w-4" />
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
              <Button
                variant="ghost"
                size="sm"
                className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-all duration-200"
                onClick={() => onSettingsClick(ch)}
              >
                <FaCog className="h-4 w-4" />
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
              <UmamiTrack 
                event={UmamiEvents.SLACK_DELETE_SOURCE_BUTTON}
                eventData={{ channelName: ch.name }}
              >
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={isDeleting || isEmbeddingActivelyProcessing(ch)}
                  className={`p-2 text-muted-foreground rounded-lg transition-all duration-200 ${
                    isDeleting || isEmbeddingActivelyProcessing(ch) 
                      ? "opacity-50 cursor-not-allowed" 
                      : "hover:text-destructive hover:bg-destructive/10"
                  }`}
                  onClick={() => !isDeleting && !isEmbeddingActivelyProcessing(ch) && onDeleteClick(ch)}
                  title={
                    isEmbeddingActivelyProcessing(ch) 
                      ? "Cannot delete channel while processing" 
                      : isDeleting 
                        ? "Deleting..." 
                        : "Delete channel"
                  }
                >
                  {isDeleting ? (
                    <FaSync className="h-4 w-4 animate-spin" />
                  ) : (
                    <FaTrash className="h-4 w-4" />
                  )}
                </Button>
              </UmamiTrack>
            </motion.div>
          </div>
        );
      },
      meta: { align: "right" },
    },
  ];
}
