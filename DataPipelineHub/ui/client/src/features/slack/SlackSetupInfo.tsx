import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Info, 
  Puzzle, 
  MessageSquare, 
  ArrowRight,
  CheckCircle,
  Copy,
  Check,
  ExternalLink,
  Settings,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

interface SlackSetupInfoProps {
  className?: string;
}

export const SlackSetupInfo = ({ className = '' }: SlackSetupInfoProps) => {
  const { toast } = useToast();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isNoticeCopied, setIsNoticeCopied] = useState(false);

  const copyTagUser = () => {
    navigator.clipboard.writeText('TAG-001');
    setIsCopied(true);
    
    toast({
      title: "Copied!",
      description: "TAG-001 has been copied to your clipboard",
      variant: "default",
    });

    // Reset the icon back to copy after 3 seconds
    setTimeout(() => {
      setIsCopied(false);
    }, 3000);
  };

  const consentNotice = [
    "Please be advised that this channel is now monitored by an AI tool for content analysis.",
    "This tool anonymously collects and embeds message content for processing.",
    "Your individual messages will not be linked to your identity.",
    "If you do not consent to this anonymous data collection, please opt out by leaving the channel."
  ].join("\n\n");

  const copyConsentNotice = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(consentNotice);
    setIsNoticeCopied(true);
    toast({
      title: "Copied!",
      description: "The channel notice has been copied to your clipboard.",
      variant: "default",
    });
    setTimeout(() => setIsNoticeCopied(false), 3000);
  };

  const steps = [
    {
      icon: Settings,
      title: "Open Channel Details",
      description: "Navigate to your channel and click on the channel name, then select 'Integrations'",
      status: "required"
    },
    {
      icon: Puzzle,
      title: "Add TAG-001 App",
      description: "Search for and add the TAG-001 app from the Apps section",
      status: "required"
    },
    {
      icon: MessageSquare,
      title: "App Access Granted",
      description: "The app will automatically gain access to channel messages",
      status: "automatic"
    },
    {
      icon: CheckCircle,
      title: "Ready for Embedding",
      description: "Your channel is now ready for message extraction and embedding",
      status: "success"
    }
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={className}
    >
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 relative shadow-lg cursor-pointer hover:shadow-xl transition-all duration-200">
        <CardContent className="p-6" onClick={() => setIsExpanded(!isExpanded)}>
          {/* Toggle Button */}
          <div className="absolute top-4 right-4 h-8 w-8 flex items-center justify-center text-muted-foreground transition-all duration-200">
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </div>

          {/* Header */}
          <div className="flex items-start space-x-4 mb-6 pr-8">
            <div className="flex-shrink-0">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shadow-sm">
                <Info className="w-6 h-6 text-primary" />
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Channel App Integration Required
              </h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                To successfully fetch and embed channel messages, you need to add the TAG-001 app to your Slack channels through the Integrations tab.
              </p>
            </div>
          </div>

          {/* Expandable Content */}
          <motion.div
            initial={false}
            animate={{
              height: isExpanded ? "auto" : 0,
              opacity: isExpanded ? 1 : 0
            }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            style={{ overflow: "hidden" }}
          >
            {/* TAG App Section */}
            <Alert className="mb-6 border-amber-500/20 bg-amber-500/5 shadow-sm">
              <AlertDescription className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-amber-600 dark:text-amber-400 font-medium">
                    Required Slack App:
                  </span>
                  <Badge 
                    variant="secondary" 
                    className="bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20 font-mono text-sm shadow-sm"
                  >
                    TAG-001
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    copyTagUser();
                  }}
                  className={`text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 hover:text-amber-700 dark:hover:text-amber-300 transition-all duration-200 ${
                    isCopied ? 'text-green-600 dark:text-green-400' : ''
                  }`}
                >
                  {isCopied ? (
                    <Check className="w-4 h-4 mr-1" />
                  ) : (
                    <Copy className="w-4 h-4 mr-1" />
                  )}
                  {isCopied ? 'Copied!' : 'Copy'}
                </Button>
              </AlertDescription>
            </Alert>

            {/* Steps */}
            <div className="space-y-4 mb-6">
              <h4 className="text-sm font-semibold text-foreground mb-3">
                Setup Process:
              </h4>
              {steps.map((step, index) => {
                const StepIcon = step.icon;
                return (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-center space-x-4 p-3 rounded-lg bg-card border border-border shadow-sm backdrop-blur-sm"
                  >
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm
                      ${step.status === 'required' ? 'bg-primary/10 text-primary' :
                        step.status === 'automatic' ? 'bg-muted text-muted-foreground' :
                        'bg-green-500/10 text-green-600 dark:text-green-400'}
                    `}>
                      <StepIcon className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-foreground text-sm">
                          {step.title}
                        </span>
                        {step.status === 'required' && (
                          <Badge variant="outline" className="text-xs text-primary border-primary/30 bg-primary/5">
                            Action Required
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {step.description}
                      </p>
                    </div>
                    {index < steps.length - 1 && (
                      <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    )}
                  </motion.div>
                );
              })}
            </div>

            {/* Consent/Monitoring Notice - shown after "App Access Granted" step */}
            <div className="mb-6">
              <div className="flex items-start justify-between p-4 rounded-lg bg-muted/40 border border-border shadow-sm">
                <div className="pr-3">
                  <h5 className="text-sm font-semibold text-foreground mb-2">
                    Channel Notice
                  </h5>
                  <p className="text-xs text-red-600 dark:text-red-400 mb-2">
                    Past this message in the channel after app access is granted:
                  </p>
                  <pre className="text-xs whitespace-pre-wrap bg-background/60 p-3 rounded-md border border-border/50">
{consentNotice}
                  </pre>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyConsentNotice}
                  className={`ml-3 self-start ${
                    isNoticeCopied ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'
                  }`}
                >
                  {isNoticeCopied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
                  {isNoticeCopied ? 'Copied!' : 'Copy'}
                </Button>
              </div>
            </div>

            {/* Help Link */}
            <div className="flex items-center justify-between pt-4 border-t border-border">
              <div className="text-xs text-muted-foreground">
                Need help adding apps to Slack channels?
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-primary hover:bg-primary/10 hover:text-primary"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open('https://slack.com/help/articles/16583775096083-Automations--What-is-a-Slack-workflow', '_blank');
                }}
              >
                <ExternalLink className="w-3 h-3 mr-1" />
                View Guide
              </Button>
            </div>
          </motion.div>
        </CardContent>
      </Card>
    </motion.div>
  );
};