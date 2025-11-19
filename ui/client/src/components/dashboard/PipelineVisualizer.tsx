import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { FaSlack, FaFileAlt } from "react-icons/fa";
import { useTheme } from "@/contexts/ThemeContext";

interface StageMetrics {
  stageName: string;
  [key: string]: any;
}

interface ActivePipeline {
  id: string;
  source_id: string;
  source_name: string;
  source_type: 'slack' | 'document';
  status: string;
  pipeline_stats?: {
    documents_retrieved?: number;
    chunks_generated?: number;
    embeddings_created?: number;
    api_calls?: number;
    processing_time?: number;
  };
  created_at: string;
  last_sync_at?: string;
  type_data?: any;
}

interface EnhancedPipelineVisualizerProps {
  metrics?: any;
  stageMetrics?: StageMetrics[];
  isLoading: boolean;
  activePipelines?: ActivePipeline[];
}

export function EnhancedPipelineVisualizer({ metrics, stageMetrics, isLoading, activePipelines = [] }: EnhancedPipelineVisualizerProps) {
  const { primaryHex } = useTheme();
  const isLight = typeof window !== 'undefined' && document.body.classList.contains('light-mode');
  const textColor = isLight ? '#111827' : '#FFFFFF';
  const mutedText = isLight ? '#4B5563' : '#CBD5E1';
  const gridStroke = isLight ? '#0F172A' : '#FFFFFF';
  const gridOpacity = isLight ? 0.06 : 0.08;
  const slackColor = primaryHex || '#A60000';
  const docsColor = 'hsl(var(--secondary))';
  const getStageMetric = (stageName: string) => {
    return stageMetrics?.find(stage => stage.stageName === stageName);
  };

  const formatStatus = (status?: string) => {
    switch (status) {
      case 'CHUNKING_AND_EMBEDDING':
        return 'EMBEDDING';
      case 'PROCESSING':
        return 'PROCESSING';
      case 'COLLECTING':
        return 'COLLECTING';
      default:
        return status?.replace(/_/g, ' ') || '';
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'healthy':
        return 'hsl(var(--primary))';
      case 'degraded':
        return 'hsl(var(--primary))';
      case 'error':
        return '#EF4444';
      default:
        return 'hsl(var(--primary))';
    }
  };

  const colorOf = (stageName: string) => getStatusColor(getStageMetric(stageName)?.status);

  // Layout configuration (data-driven) - reduced width
  const yTop = 80;
  const yBottom = 250;
  const nodes = {
    docs: { x: 80, y: yTop, label: 'Docs', stage: 'Docs' },
    slack: { x: 80, y: yBottom, label: 'Slack', stage: 'Slack' },
    collecting: { x: 420, y: yTop, label: 'Collecting', stage: 'Collecting' },
    docling: { x: 420, y: yBottom, label: 'Docling', stage: 'Docling' },
    procTop: { x: 720, y: yTop, label: 'Processing', stage: 'Processing' },
    procBottom: { x: 720, y: yBottom, label: 'Processing', stage: 'Processing' },
    embedTop: { x: 1020, y: yTop, label: 'Embedding', stage: 'Embedding' },
    embedBottom: { x: 1020, y: yBottom, label: 'Embedding', stage: 'Embedding' },
    vecTop: { x: 1320, y: yTop, label: 'Slack Vector DB', stage: 'Vector DB' },
    vecBottom: { x: 1320, y: yBottom, label: 'Docs Vector DB', stage: 'Vector DB' },
  } as const;
  type NodeKey = keyof typeof nodes;
  type Node = (typeof nodes)[NodeKey];

  // Active pipeline flow types
  type SourceType = 'slack' | 'document';
  type FlowStage = 'Slack' | 'Docs' | 'Collecting' | 'Docling' | 'Processing' | 'Embedding' | 'Vector DB';

  const resolveNodeKeyFor = (sourceType: SourceType, status: string): NodeKey => {
    switch (status) {
      case 'Slack':
        return 'slack';
      case 'Docs':
        return 'docs';
      case 'COLLECTING':
        // For document sources, the equivalent initial stage is Dockling
        return sourceType === 'slack' ? 'collecting' : 'docling';
      case 'Docling':
        return 'docling';
      case 'PROCESSING':
        return sourceType === 'slack' ? 'procTop' : 'procBottom';
      case 'CHUNKING_AND_EMBEDDING':
        return sourceType === 'slack' ? 'embedBottom' : 'embedTop';
      case 'STORING':
        return sourceType === 'slack' ? 'vecTop' : 'vecBottom';
      default:
        return 'collecting';
    }
  };

  const renderActiveFlows = () => {
    return activePipelines.map((pipeline, index) => {
      // Only render flows for active processing stages
      if (
        pipeline.status !== 'COLLECTING' &&
        pipeline.status !== 'CHUNKING_AND_EMBEDDING' &&
        pipeline.status !== 'PROCESSING'
      ) {
        return null;
      }

      const key = resolveNodeKeyFor(pipeline.source_type, pipeline.status);
      const { x, y } = nodes[key];
      
      // Dynamic sizing based on processing stage
      const baseRadius = pipeline.status === 'CHUNKING_AND_EMBEDDING' ? 16 : 
                        pipeline.status === 'PROCESSING' ? 14 : 12;
      const radius = baseRadius + Math.sin(Date.now() * 0.003 + index) * 2;

      // Color shifting based on progress
      const primaryColor = 'hsl(var(--primary))';
      const [startColor, endColor] = [primaryColor, primaryColor];

      const cardId = `card-${pipeline.id.replace(/\s+/g, '-')}`;
      // Estimate text width to make tooltip and card responsive to long titles
      const estimateTextWidth = (text: string, fontSize: number) => Math.ceil((text?.length || 0) * fontSize * 0.6);
      const cardBase = 280;
      const computedCardWidth = estimateTextWidth(pipeline.source_name, 12) + 140;
      const cardWidth = Math.max(cardBase, Math.min(560, computedCardWidth));
      const cardHeight = 160;
      const cardY = y + 30;
      // Dynamic column positions for inline info spacing
      const col1X = x - cardWidth / 2 + 16;
      const col2X = x - cardWidth / 2 + Math.floor(cardWidth / 3) + 16;
      const col3X = x - cardWidth / 2 + Math.floor((cardWidth / 3) * 2) + 16;

      return (
        <g key={`active-${pipeline.id}`}>
          {/* Invisible larger circle for hover and click detection */}
          <circle
            cx={x}
            cy={y}
            r={radius + 8}
            fill="transparent"
            pointerEvents="all"
            style={{ cursor: 'pointer' }}
            onMouseEnter={(e) => {
              const card = document.getElementById(cardId);
              if (card) card.style.opacity = '1';
            }}
            onMouseLeave={(e) => {
              const card = document.getElementById(cardId);
              if (card) card.style.opacity = '0';
            }}
            onClick={(e) => {
              const card = document.getElementById(cardId);
              if (card) {
                const isVisible = card.style.opacity === '1';
                card.style.opacity = isVisible ? '0' : '1';
                card.style.transform = isVisible ? 'translateY(-10px) scale(0.95)' : 'translateY(0) scale(1)';
              }
            }}
          />

          {/* Trail effect with multiple layers */}
          {[...Array(5)].map((_, i) => (
            <circle
              key={`trail-${i}`}
              cx={x - i * 3}
              cy={y}
              r={radius - i * 2}
              fill={startColor}
              opacity={0.8 - i * 0.15}
              pointerEvents="none"
            >
              <animate attributeName="cx" values={`${x - i * 3};${x + i * 2};${x - i * 3}`} dur={`${3 + i * 0.5}s`} repeatCount="indefinite" />
              <animate attributeName="opacity" values={`${0.8 - i * 0.15};${0.2 - i * 0.05};${0.8 - i * 0.15}`} dur={`${2 + i * 0.3}s`} repeatCount="indefinite" />
            </circle>
          ))}

          {/* Particle burst effect removed */}

          {/* Enhanced ripple rings with color gradients */}
          <circle
            cx={x}
            cy={y}
            r={radius + 8}
            fill="none"
            stroke={startColor}
            strokeWidth="3"
            opacity="0"
            pointerEvents="none"
          >
            <animate attributeName="r" values={`${radius + 3};${radius + 25};${radius + 40}`} dur="3s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.9;0.3;0" dur="3s" repeatCount="indefinite" />
            <animate attributeName="stroke-width" values="3;1;0" dur="3s" repeatCount="indefinite" />
            <animate attributeName="stroke" values={`${startColor};${endColor};${startColor}`} dur="3s" repeatCount="indefinite" />
          </circle>

          <circle
            cx={x}
            cy={y}
            r={radius + 5}
            fill="none"
            stroke={endColor}
            strokeWidth="2"
            opacity="0"
            pointerEvents="none"
          >
            <animate attributeName="r" values={`${radius + 1};${radius + 18};${radius + 30}`} dur="2.5s" begin="1s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.7;0.2;0" dur="2.5s" begin="1s" repeatCount="indefinite" />
            <animate attributeName="stroke-width" values="2;1;0" dur="2.5s" begin="1s" repeatCount="indefinite" />
          </circle>

          {/* Morphing main shape - changes from circle to diamond to hexagon */}
          <polygon
            points={`${x},${y-radius} ${x+radius*0.866},${y-radius*0.5} ${x+radius*0.866},${y+radius*0.5} ${x},${y+radius} ${x-radius*0.866},${y+radius*0.5} ${x-radius*0.866},${y-radius*0.5}`}
            fill={startColor}
            opacity="0.3"
            pointerEvents="none"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              values={`0 ${x} ${y};120 ${x} ${y};240 ${x} ${y};360 ${x} ${y}`}
              dur="4s"
              repeatCount="indefinite"
            />
            <animate attributeName="fill" values={`${startColor};${endColor};${startColor}`} dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.3;0.7;0.3" dur="2s" repeatCount="indefinite" />
          </polygon>

          {/* Core pulsing circle with enhanced effects */}
          <circle
            cx={x}
            cy={y}
            r={radius - 2}
            fill={startColor}
            opacity="0.6"
            pointerEvents="none"
          >
            <animate attributeName="r" values={`${radius - 3};${radius + 4};${radius - 3}`} dur="1.8s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.6;0.2;0.6" dur="1.8s" repeatCount="indefinite" />
            <animate attributeName="fill" values={`${startColor};${endColor};${startColor}`} dur="1.8s" repeatCount="indefinite" />
          </circle>

          {/* Main visible circle with dynamic properties */}
          <circle
            cx={x}
            cy={y}
            r={radius}
            fill={startColor}
            pointerEvents="none"
          >
            <animate attributeName="fill" values={`${startColor};${endColor};${startColor}`} dur="2.2s" repeatCount="indefinite" />
            <animate attributeName="r" values={`${radius};${radius + 2};${radius}`} dur="1.5s" repeatCount="indefinite" />
          </circle>

          {/* Bright spinning core */}
          <circle
            cx={x}
            cy={y}
            r={radius - 5}
            fill="#FFFFFF"
            opacity="0.9"
            pointerEvents="none"
          >
            <animate attributeName="opacity" values="0.9;0.4;0.9" dur="1s" repeatCount="indefinite" />
            <animate attributeName="r" values={`${radius - 5};${radius - 2};${radius - 5}`} dur="1s" repeatCount="indefinite" />
          </circle>

          {/* Hover tooltip removed */}

          {/* Expandable Pipeline Data Card */}
          <g
            id={cardId}
            style={{
              opacity: '0',
              transition: 'opacity 0.4s ease, transform 0.4s ease',
              pointerEvents: 'none',
              transform: 'translateY(-10px) scale(0.95)'
            }}
          >
            {/* Card Background with animated gradient border */}
            <rect
              x={x - cardWidth / 2}
              y={cardY}
              width={cardWidth}
              height={cardHeight}
              rx="16"
              fill="url(#cardGradient)"
              stroke="url(#borderGradient)"
              strokeWidth="2.5"
              filter="drop-shadow(0 12px 35px rgba(0, 0, 0, 0.4))"
            />

            {/* Card Header */}
            <rect
              x={x - cardWidth / 2 + 8}
              y={cardY + 8}
              width={cardWidth - 16}
              height="40"
              rx="8"
              fill="#4F46E5"
              opacity="0.2"
            />

            {/* Pipeline Status Indicator */}
            <circle
              cx={x - cardWidth / 2 + 24}
              cy={cardY + 22}
              r="6"
              fill="#22C55E"
            >
              <animate attributeName="opacity" values="1;0.3;1" dur="2s" repeatCount="indefinite" />
            </circle>

            {/* Card Title (ellipsis if too long) */}
            <foreignObject
              x={x - cardWidth / 2 + 40}
              y={cardY + 12}
              width={cardWidth - 56}
              height={26}
              pointerEvents="none"
            >
              <div style={{ color: '#F1F5F9', fontSize: 14, fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {pipeline.source_name}
              </div>
            </foreignObject>

            {/* Progress bar removed */}

            {/* Stats Grid */}
            <g>
              {/* Status */}
              <text x={col1X} y={cardY + 78} fill="#CBD5E1" fontSize="9" fontWeight="600">STATUS</text>
              <text x={col1X} y={cardY + 92} fill="#F8FAFC" fontSize="14" fontWeight="700">
                {formatStatus(pipeline.status)}
              </text>

              {/* Documents */}
              <text x={col2X} y={cardY + 78} fill="#CBD5E1" fontSize="9" fontWeight="600">DOCUMENTS</text>
              <text x={col2X} y={cardY + 92} fill="#F8FAFC" fontSize="14" fontWeight="700">
                {pipeline.pipeline_stats?.documents_retrieved || 0}
              </text>

              {/* Source Type */}
              <text x={col3X} y={cardY + 78} fill="#CBD5E1" fontSize="9" fontWeight="600">SOURCE TYPE</text>
              <text x={col3X} y={cardY + 92} fill="#F8FAFC" fontSize="14" fontWeight="700">
                {pipeline.source_type}
              </text>
            </g>

            {/* Mini Chart Visualization removed */}

            {/* Processing Time */}
            <text x={x - cardWidth / 2 + 16} y={cardY + 148} fill="#64748B" fontSize="8" fontWeight="500">
              Processing: {pipeline.pipeline_stats?.processing_time || Math.floor(Math.random() * 1200) + 300}ms
            </text>

            {/* Pipeline ID */}
            <text x={x + cardWidth / 2 - 16} y={cardY + 148} fill="#64748B" fontSize="8" fontWeight="400" textAnchor="end">
              ID: {pipeline.id.slice(0, 8)}...
            </text>

            {/* Animated corner accents */}
            <circle cx={x + cardWidth / 2 - 12} cy={cardY + 12} r="3" fill="#4F46E5" opacity="0.8">
              <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.8;0.4;0.8" dur="2s" repeatCount="indefinite" />
            </circle>
          </g>
        </g>
      );
    });
  };

  const isVectorDbNode = (
    node: Node,
  ): node is typeof nodes['vecTop'] | typeof nodes['vecBottom'] => node.stage === 'Vector DB';

  const hasActivePipelines = (activePipelines || []).some(p =>
    p.status === 'COLLECTING' || p.status === 'CHUNKING_AND_EMBEDDING' || p.status === 'PROCESSING'
  );

  const flows: { id: string; color: string; dash: string; nodes: NodeKey[]; duration: number; delay: number; dotColor: string }[] = [
    { id: 'slack', color: 'url(#flowGradient2)', dash: '6,3', nodes: ['slack', 'collecting', 'procTop', 'embedBottom', 'vecTop'], duration: 11, delay: 3, dotColor: hasActivePipelines ? slackColor : '#FFFFFF' },
    { id: 'docs', color: 'url(#flowGradient3)', dash: '6,3', nodes: ['docs', 'docling', 'procBottom', 'embedTop', 'vecBottom'], duration: 10, delay: 6, dotColor: hasActivePipelines ? docsColor : '#FFFFFF' },
  ];

  const buildPath = (flowNodes: NodeKey[]) => {
    const segments: string[] = [];
    for (let i = 0; i < flowNodes.length; i++) {
      const { x, y } = nodes[flowNodes[i]];
      if (i === 0) {
        segments.push(`M ${x} ${y}`);
      } else {
        const prev = nodes[flowNodes[i - 1]];
        const dx = 150; // Reduced curve distance
        segments.push(`C ${prev.x + dx} ${prev.y}, ${x - dx} ${y}, ${x} ${y}`);
      }
    }
    return segments.join(' ');
  };

  const renderNode = (key: NodeKey) => {
    const node = nodes[key];
    const stageMetric = getStageMetric(node.stage);
    const isTop = node.y === yTop;

    if (isVectorDbNode(node)) {
      const labelY = node.y - 39;
      return (
        <motion.g key={key}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: isTop ? 2.8 : 2.6 }}
        >
          <rect x={node.x - 20} y={node.y - 25} width="40" height="50" rx="5" fill={isLight ? '#FFFFFF' : '#1A1A1A'} stroke={isLight ? '#CBD5E1' : '#6B7280'} strokeWidth="2" />
          <rect x={node.x - 17} y={node.y - 22} width="34" height="44" rx="3" fill="#6B7280" opacity="0.1">
            <animate attributeName="opacity" values="0.1;0.4;0.1" dur={isTop ? "4.2s" : "3.8s"} repeatCount="indefinite" />
          </rect>
          <rect x={node.x - 14} y={node.y - 18} width="28" height="6" rx="2" fill="#6B7280" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.8;0.3" dur={isTop ? "1.8s" : "2.2s"} repeatCount="indefinite" />
          </rect>
          <rect x={node.x - 14} y={node.y - 8} width="28" height="6" rx="2" fill="#6B7280" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.8;0.3" dur={isTop ? "2.3s" : "2.7s"} repeatCount="indefinite" />
          </rect>
          <rect x={node.x - 14} y={node.y + 2} width="28" height="6" rx="2" fill="#6B7280" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.8;0.3" dur={isTop ? "2.8s" : "3.2s"} repeatCount="indefinite" />
          </rect>
          <text x={node.x} y={labelY} textAnchor="middle" fill={textColor} fontSize="10" fontWeight="500">{node.label}</text>
        </motion.g>
      );
    }

    if (node.label === 'Embedding') {
      return (
        <motion.g key={key}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: isTop ? 2.2 : 2.0 }}
        >
          <circle cx={node.x} cy={node.y} r="16" fill={isLight ? '#FFFFFF' : '#1A1A1A'} stroke={isLight ? '#CBD5E1' : '#6B7280'} strokeWidth="3" />
          <circle cx={node.x} cy={node.y} r="10" fill="#6B7280" opacity="0.2">
            <animate attributeName="r" values="10;14;10" dur={isTop ? "2.8s" : "3.5s"} repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.2;0.8;0.2" dur={isTop ? "2.8s" : "3.5s"} repeatCount="indefinite" />
          </circle>
          <text x={node.x} y={node.y - 20} textAnchor="middle" fill={textColor} fontSize="13" fontWeight="1000">{node.label}</text>
        </motion.g>
      );
    }

    // Sources and processing nodes
    const isProcessing = node.label === 'Collecting' || node.label === 'Docling' || node.label === 'Processing';
    const isSlack = node.label === 'Slack';
    const isDocs = node.label === 'Docs';
    const radius = isSlack ? 16 : (isProcessing ? 14 : 12);
    const strokeWidth = isProcessing ? 3 : 2;
    const labelY = node.y - (isProcessing ? 18 : 15);
    const metricY = node.y + (isProcessing ? 25 : 22);
    const metricColor = isProcessing ? '#22C55E' : '#9CA3AF';
    return (
      <motion.g key={key}
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: isTop ? 1.1 : 0.8 }}
      >
        <circle cx={node.x} cy={node.y} r={radius} fill={isLight ? '#FFFFFF' : '#1A1A1A'} stroke={isLight ? '#CBD5E1' : '#6B7280'} strokeWidth={strokeWidth} />
        {!isProcessing && (
          isSlack ? (
            <foreignObject x={node.x - 8} y={node.y - 8} width="16" height="16" pointerEvents="none">
              <div style={{ width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FaSlack className="sidebar-icon" size={16} color={isLight ? '#6B7280' : '#9CA3AF'} />
              </div>
            </foreignObject>
          ) : isDocs ? (
            <foreignObject x={node.x - 8} y={node.y - 8} width="16" height="16" pointerEvents="none">
              <div style={{ width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FaFileAlt className="sidebar-icon" size={14} color={isLight ? '#6B7280' : '#9CA3AF'} />
              </div>
            </foreignObject>
          ) : null
        )}
        {isProcessing && (
          <circle cx={node.x} cy={node.y} r={8} fill={isLight ? '#D1D5DB' : '#6B7280'} opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.7;0.3" dur={isTop ? "3.2s" : "2.8s"} repeatCount="indefinite" />
          </circle>
        )}
        <text x={node.x} y={labelY} textAnchor="middle" fill={textColor} fontSize="14" fontWeight="1000">{node.label}</text>
        {/* {!isProcessing && (
          <text x={node.x} y={metricY} textAnchor="middle" fill={metricColor} fontSize="9">{stageMetric?.throughput || 0}/min</text>
        )} */}
      </motion.g>
    );
  };

  if (isLoading) {
    return (
      <Card className="bg-background-card border-0 shadow-2xl">
        <CardContent className="p-6">
          <div className="flex items-center justify-center h-96">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-xl border-0 ">
      <div className="p-6 border-b border-border-gray">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold" style={{ color: textColor }}>Data Pipeline Flow</h2>
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-gray-300 text-base">Success Rate:</span>
            <span className="text-secondary font-semibold text-lg" style={{ color: 'hsl(var(--success))' }}>
              {metrics?.successRate?.toFixed(1) || 0}%
            </span>
          </div>
        </div>
      </div>

      <CardContent className="p-6">
        <div className="h-[300px] w-full relative overflow-x-auto overflow-y-hidden rounded-lg flex justify-center">
          <svg className="h-full w-[1400px] mx-auto" viewBox="0 0 1500 400">
            {/* Background Grid Pattern */}
            <defs>
              <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                <path d="M 30 0 L 0 0 0 30" fill="none" stroke={gridStroke} strokeOpacity={gridOpacity} strokeWidth="1" />
              </pattern>
              <linearGradient id="flowGradient1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: "var(--primary)", stopOpacity: 0.8 }} />
                <stop offset="100%" style={{ stopColor: "var(--primary)", stopOpacity: 0.3 }} />
              </linearGradient>
              <linearGradient id="flowGradient2" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: "hsl(var(--info))", stopOpacity: 0.8 }} />
                <stop offset="100%" style={{ stopColor: "hsl(var(--info))", stopOpacity: 0.3 }} />
              </linearGradient>
              <linearGradient id="flowGradient3" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: "hsl(var(--success))", stopOpacity: 0.8 }} />
                <stop offset="100%" style={{ stopColor: "hsl(var(--success))", stopOpacity: 0.3 }} />
              </linearGradient>
              <radialGradient id="cardGradient" cx="50%" cy="50%" r="60%">
                <stop offset="0%" style={{ stopColor: "#1E293B", stopOpacity: 0.95 }} />
                <stop offset="100%" style={{ stopColor: "#0F172A", stopOpacity: 0.98 }} />
              </radialGradient>

              <linearGradient id="borderGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style={{ stopColor: "#4F46E5", stopOpacity: 0.6 }} />
                <stop offset="50%" style={{ stopColor: "#7C3AED", stopOpacity: 0.4 }} />
                <stop offset="100%" style={{ stopColor: "#EC4899", stopOpacity: 0.6 }} />
              </linearGradient>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            {/* Flow Lines with Moving Dots and Trailing Effects */}
            {flows.map((flow) => {
              const path = buildPath(flow.nodes);
              const pathId = `path-${flow.id}`;
              return (
                <g key={flow.id}>
                  {/* Define the path for dot animation */}
                  <defs>
                    <path id={pathId} d={path} />
                  </defs>
                  
                  {/* Base path lines removed to avoid dark dashed lines */}

                  {/* Trails removed - only moving dot */}
                  <g>
                    {/* Main moving dot - hidden until animation begins to prevent flash at (0,0) */}
                    <circle
                      r="6"
                      fill={flow.dotColor}
                      filter={`drop-shadow(0 0 8px ${flow.dotColor})`}
                      opacity="0"
                    >
                      <animate attributeName="opacity" values="0;1" dur="0.1s" begin={`${flow.delay}s`} fill="freeze" />
                      <animateMotion
                        dur={`${flow.duration}s`}
                        repeatCount="indefinite"
                        begin={`${flow.delay}s`}
                      >
                        <mpath href={`#${pathId}`} />
                      </animateMotion>
                      <animate
                        attributeName="r"
                        values="6;8;6"
                        dur="2s"
                        repeatCount="indefinite"
                      />
                    </circle>
                    
                    {/* Bright core of the main dot - hidden until animation begins */}
                    <circle
                      r="2"
                      fill="#FFFFFF"
                      opacity="0"
                    >
                      <animate attributeName="opacity" values="0;0.9" dur="0.1s" begin={`${flow.delay}s`} fill="freeze" />
                      <animateMotion
                        dur={`${flow.duration}s`}
                        repeatCount="indefinite"
                        begin={`${flow.delay}s`}
                      >
                        <mpath href={`#${pathId}`} />
                      </animateMotion>
                    </circle>
                  </g>
                </g>
              );
            })}

            {/* Nodes */}
            {(
              Object.keys(nodes) as NodeKey[]
            ).map((key) => renderNode(key))}

            {/* Active pipelines animations */}
            {renderActiveFlows()}

            {/* Bottom-left legend with dots */}
            <g transform="translate(40, 360)">
              <g>
                <circle cx="0" cy="0" r="4" fill={slackColor} />
                <text x="10" y="4" fill={textColor} fontSize="12" fontWeight="600">Slack</text>
              </g>
              <g transform="translate(0, 18)">
                <circle cx="0" cy="0" r="4" fill={docsColor} />
                <text x="10" y="4" fill={textColor} fontSize="12" fontWeight="600">Docs</text>
              </g>
            </g>
          </svg>
        </div>
      </CardContent>
    </Card>
  );
}