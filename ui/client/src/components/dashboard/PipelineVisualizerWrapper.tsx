import { useEffect, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { EnhancedPipelineVisualizer } from './PipelineVisualizer';
import { fetchActivePipelines, fetchPipelineMetrics, type ActivePipeline, type PipelineMetrics } from '@/api/pipelines';
import { PIPELINE_STATUS } from '@/constants/pipelineStatus';
import { isEmbeddingActivelyProcessing } from '@/features/helpers';

interface PipelineVisualizerWrapperProps {
  refreshInterval?: number; // in milliseconds
}

export function PipelineVisualizerWrapper({ refreshInterval = 5000 }: PipelineVisualizerWrapperProps) {
  const [activeFlows, setActiveFlows] = useState<ActivePipeline[]>([]);

  // Helper function to check if there are active operations
  const hasActiveOperations = (pipelines: ActivePipeline[] | undefined) => {
    if (!pipelines || !Array.isArray(pipelines)) return false;
    
    return pipelines.some(pipeline => 
      isEmbeddingActivelyProcessing(pipeline as any)
    );
  };

  // Fetch active pipelines with smart real-time updates
  const { data: pipelines = [], isLoading, error } = useQuery({
    queryKey: ['activePipelines'],
    queryFn: fetchActivePipelines,
    staleTime: 15 * 1000, // Consider data stale after 15 seconds
    refetchOnMount: true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data as ActivePipeline[] | undefined;
      const hasActive = hasActiveOperations(data);
      return hasActive ? 5000 : false; // Only refetch every 5 seconds if there are active pipelines
    },
  });

  // Fetch pipeline metrics with smart real-time updates
  const { data: metrics } = useQuery({
    queryKey: ['pipelineMetrics'],
    queryFn: fetchPipelineMetrics,
    staleTime: 10 * 1000, // Consider metrics stale after 10 seconds
    refetchOnMount: true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data as ActivePipeline[] | undefined;
      const hasActive = hasActiveOperations(data);
      return hasActive ? 10000 : false; // Only refetch every 10 seconds if there are active pipelines
    },
  });

  // Process active flows for visualization
  useEffect(() => {
    if (pipelines.length > 0) {
      setActiveFlows(pipelines);
    }
  }, [pipelines]);

  // Create stage metrics for the visualizer
  const stageMetrics = useCallback(() => {
    const stages = ['Collecting', 'Processing', 'Embedding', 'Vector DB'];
    return stages.map(stage => {
      const stagePipelines = activeFlows.filter(pipeline => {
        switch (stage) {
          case 'Collecting':
            return pipeline.status === PIPELINE_STATUS.COLLECTING;
          case 'Processing':
            return pipeline.status === PIPELINE_STATUS.PROCESSING;
          case 'Embedding':
            return pipeline.status === PIPELINE_STATUS.CHUNKING_AND_EMBEDDING;
          case 'Vector DB':
            return pipeline.status === PIPELINE_STATUS.STORING;
          default:
            return false;
        }
      });

      return {
        stageName: stage,
        count: stagePipelines.length,
        status: stagePipelines.length > 0 ? 'healthy' : 'idle',
        throughput: stagePipelines.reduce((sum, p) => sum + (p.pipeline_stats?.documents_retrieved || 0), 0),
        pipelines: stagePipelines,
      };
    });
  }, [activeFlows]);

  // Enhanced metrics with real-time data
  const enhancedMetrics = {
    ...metrics,
    activeFlows: activeFlows.length,
    stageBreakdown: stageMetrics(),
    realTimeData: true,
  };

  if (error) {
    console.error('Failed to fetch pipeline data:', error);
  }

  return (
    <EnhancedPipelineVisualizer
      metrics={enhancedMetrics}
      stageMetrics={stageMetrics()}
      isLoading={isLoading}
      activePipelines={activeFlows}
    />
  );
}
