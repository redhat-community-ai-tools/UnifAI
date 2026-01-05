import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FaSync, FaPlus } from "react-icons/fa";
import { useLocation } from "wouter";
import { motion } from "framer-motion";
import { EmbedChannel } from "@/types";
import { DataTable } from "@/components/shared/DataTable";
import { getColumns } from "./ChannelTable";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';

export interface PaginatedChannelTableProps {
  allChannels: EmbedChannel[];
  onSettingsClick: (channel: EmbedChannel) => void;
  onDeleteClick: (channel: EmbedChannel) => void;
  onRefresh: () => void;
  pageSize?: number;
  isLoading?: boolean;
  deletingChannelId?: string;
  activeEmbeddingIds?: string[];
}

export function PaginatedChannelTable({
  allChannels,
  onSettingsClick,
  onDeleteClick,
  onRefresh,
  pageSize = 6,
  isLoading = false,
  deletingChannelId,
  activeEmbeddingIds = [],
}: PaginatedChannelTableProps) {
  const [, navigate] = useLocation();
  if (isLoading) {
    return (
      <Card className="gradient-border shadow-2xl overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="h-6 w-48 rounded bg-gradient-to-r from-slate-600/20 via-slate-500/20 to-slate-600/20 bg-[length:200%_100%] animate-skeleton"></div>
            <div className="flex space-x-3">
              <div className="h-10 w-32 rounded-lg bg-gradient-to-r from-slate-600/20 via-slate-500/20 to-slate-600/20 bg-[length:200%_100%] animate-skeleton"></div>
              <div className="h-10 w-40 rounded-lg bg-gradient-to-r from-slate-600/20 via-slate-500/20 to-slate-600/20 bg-[length:200%_100%] animate-skeleton"></div>
            </div>
          </div>
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-12 w-full rounded-lg bg-gradient-to-r from-slate-600/20 via-slate-500/20 to-slate-600/20 bg-[length:200%_100%] animate-skeleton"
              ></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="w-full"
    >
      <Card className="gradient-border shadow-2xl overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-foreground">
              Channel Status Dashboard
            </h3>
            <div className="flex items-center space-x-3">
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <UmamiTrack 
                  event={UmamiEvents.SLACK_ADD_SOURCE_BUTTON}
                >
                  <Button
                    onClick={() => navigate("/slack/add-source")}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 hover:-translate-y-0.5 hover:scale-105 hover:shadow-lg transition-all duration-200"
                  >
                    <FaPlus className="mr-2" /> Add Channel
                  </Button>
                </UmamiTrack>
              </motion.div>
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <Button
                  variant="outline"
                  onClick={onRefresh}
                  className="px-4 py-2 border border-border text-foreground rounded-lg font-medium hover:bg-muted hover:-translate-y-0.5 hover:scale-105 hover:shadow-lg transition-all duration-200"
                >
                  <FaSync className="mr-2" /> Refresh Status
                </Button>
              </motion.div>
            </div>
          </div>

          <div
            className="overflow-x-auto
              [&_table]:border-collapse
              [&_thead_tr]:!border-b-[0.5px] [&_thead_tr]:!border-gray-500/20
              [&_tbody_tr]:!border-b-[0.5px] [&_tbody_tr]:!border-gray-500/15"
          >
            <DataTable
              columns={getColumns(onSettingsClick, onDeleteClick, deletingChannelId, activeEmbeddingIds)}
              data={allChannels}
              enableSorting={true}
              enableColumnFilters={true}
              enablePagination={true}
              initialState={{
                pagination: { pageIndex: 0, pageSize: 8 },
                sorting: [],
              }}
            />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
} 