import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { FaSlack, FaSync, FaDatabase, FaChartBar, FaPlus, FaSearch, FaTimes, FaCog } from "react-icons/fa";
import { motion } from "framer-motion";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tooltip } from "@/components/ui/tooltip";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function SlackIntegration() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  
  const handleConnect = () => {
    setIsConnecting(true);
    setTimeout(() => {
      setIsConnecting(false);
    }, 2000);
  };

  const handleSelectChannel = (channel: string) => {
    if (selectedChannels.includes(channel)) {
      setSelectedChannels(selectedChannels.filter(c => c !== channel));
    } else {
      setSelectedChannels([...selectedChannels, channel]);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Slack Integration"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Tabs defaultValue="add-source" className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger
                  value="add-source"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <FaPlus className="mr-2" />
                  Add Source
                </TabsTrigger>
                <TabsTrigger
                  value="available-data"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <FaDatabase className="mr-2" />
                  Available Data
                </TabsTrigger>
                <TabsTrigger
                  value="channel-management"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <FaCog className="mr-2" />
                  Channel Management
                </TabsTrigger>
              </TabsList>

              <TabsContent value="add-source">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <div className="flex items-center mb-6">
                        <FaSlack className="text-secondary text-2xl mr-3" />
                        <h3 className="text-lg font-heading font-semibold">
                          Connect to Slack
                        </h3>
                      </div>

                      <div className="space-y-6">
                        <div>
                          <Label htmlFor="workspace" className="text-sm">
                            Workspace URL
                          </Label>
                          <Input
                            id="workspace"
                            placeholder="yourworkspace.slack.com"
                            className="mt-1 bg-background-dark"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            Enter your Slack resources URL
                          </p>
                        </div>

                        <div>
                          <Label htmlFor="oauth-token" className="text-sm">
                            Bot OAuth Token
                          </Label>
                          <Input
                            id="oauth-token"
                            type="password"
                            placeholder="xoxb-..."
                            className="mt-1 bg-background-dark"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            Generate a Bot User OAuth Token in your Slack App
                          </p>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <div>
                            <Label htmlFor="use-oauth" className="text-base">
                              Use OAuth
                            </Label>
                            <p className="text-xs text-gray-400 mt-1">
                              Authenticate with Slack OAuth 2.0
                            </p>
                          </div>
                          <Switch id="use-oauth" defaultChecked />
                        </div>

                        <Button
                          className="w-full bg-secondary"
                          onClick={handleConnect}
                          disabled={isConnecting}
                        >
                          {isConnecting ? (
                            <>
                              <svg
                                className="animate-spin -ml-1 mr-3 h-4 w-4 text-white"
                                xmlns="http://www.w3.org/2000/svg"
                                fill="none"
                                viewBox="0 0 24 24"
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                ></circle>
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                ></path>
                              </svg>
                              Connecting...
                            </>
                          ) : (
                            <>Connect to Slack</>
                          )}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Channel Selection
                      </h3>

                      <div className="space-y-6">
                        <div>
                          <Label htmlFor="channel-search" className="text-sm">
                            Search Channels
                          </Label>
                          <div className="relative mt-1">
                            <Input
                              id="channel-search"
                              placeholder="Search channels..."
                              className="pr-10 bg-background-dark"
                            />
                            <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                              <FaSearch className="text-gray-400" />
                            </div>
                          </div>
                        </div>

                        <div className="border border-gray-800 rounded-md h-64 overflow-y-auto bg-background-dark">
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('general')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>general</span>
                              <Badge className="ml-2 bg-secondary bg-opacity-20 text-secondary">
                                High Activity
                              </Badge>
                            </div>
                            <Switch checked={selectedChannels.includes('general')} onCheckedChange={() => handleSelectChannel('general')} />
                          </div>
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('engineering')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>engineering</span>
                            </div>
                            <Switch checked={selectedChannels.includes('engineering')} onCheckedChange={() => handleSelectChannel('engineering')} />
                          </div>
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('product')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>product</span>
                            </div>
                            <Switch checked={selectedChannels.includes('product')} onCheckedChange={() => handleSelectChannel('product')} />
                          </div>
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('design')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>design</span>
                            </div>
                            <Switch checked={selectedChannels.includes('design')} onCheckedChange={() => handleSelectChannel('design')} />
                          </div>
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('random')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>random</span>
                            </div>
                            <Switch checked={selectedChannels.includes('random')} onCheckedChange={() => handleSelectChannel('random')} />
                          </div>
                          <div className="p-3 border-b border-gray-800 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('announcements')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>announcements</span>
                            </div>
                            <Switch checked={selectedChannels.includes('announcements')} onCheckedChange={() => handleSelectChannel('announcements')} />
                          </div>
                          <div className="p-3 flex items-center justify-between hover:bg-background-surface cursor-pointer" onClick={() => handleSelectChannel('help')}>
                            <div className="flex items-center">
                              <span className="text-gray-400 mr-2">#</span>
                              <span>help</span>
                            </div>
                            <Switch checked={selectedChannels.includes('help')} onCheckedChange={() => handleSelectChannel('help')} />
                          </div>
                        </div>

                        <div className="flex justify-between items-center">
                          <span className="text-sm">
                            {selectedChannels.length} channels selected
                          </span>
                          <Button variant="outline" size="sm">
                            Select All
                          </Button>
                        </div>

                        <div>
                          <Label htmlFor="date-range" className="text-sm">
                            Date Range
                          </Label>
                          <Select defaultValue="30d">
                            <SelectTrigger
                              id="date-range"
                              className="mt-1 bg-background-dark"
                            >
                              <SelectValue placeholder="Select date range" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="7d">Last 7 days</SelectItem>
                              <SelectItem value="30d">Last 30 days</SelectItem>
                              <SelectItem value="90d">Last 90 days</SelectItem>
                              <SelectItem value="180d">Last 6 months</SelectItem>
                              <SelectItem value="365d">Last year</SelectItem>
                              <SelectItem value="all">All time</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-gray-400 mt-1">
                            How far back to fetch messages
                          </p>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <div>
                            <Label htmlFor="include-threads" className="text-base">
                              Include Threads
                            </Label>
                            <p className="text-xs text-gray-400 mt-1">
                              Process conversation threads
                            </p>
                          </div>
                          <Switch id="include-threads" defaultChecked />
                        </div>

                        <div className="flex items-center justify-between">
                          <div>
                            <Label htmlFor="include-files" className="text-base">
                              Process File Content
                            </Label>
                            <p className="text-xs text-gray-400 mt-1">
                              Extract text from shared files
                            </p>
                          </div>
                          <Switch id="include-files" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="available-data">
                <div className="grid grid-cols-1 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-heading font-semibold">
                          Conversation Explorer
                        </h3>
                        <div className="flex items-center space-x-2">
                          <Select defaultValue="all">
                            <SelectTrigger className="w-40 bg-background-dark">
                              <SelectValue placeholder="All channels" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All channels</SelectItem>
                              <SelectItem value="general">#general</SelectItem>
                              <SelectItem value="engineering">#engineering</SelectItem>
                              <SelectItem value="product">#product</SelectItem>
                              <SelectItem value="design">#design</SelectItem>
                            </SelectContent>
                          </Select>
                          <Input
                            placeholder="Search messages..."
                            className="w-64 bg-background-dark"
                          />
                        </div>
                      </div>

                      <div className="space-y-6">
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800">
                          <div className="flex items-start space-x-3">
                            <Avatar className="h-8 w-8 mt-1">
                              <AvatarImage src="" />
                              <AvatarFallback className="bg-primary text-white">AK</AvatarFallback>
                            </Avatar>
                            <div className="flex-1">
                              <div className="flex items-center">
                                <span className="font-medium">Alex Kim</span>
                                <span className="text-xs text-gray-400 ml-2">#engineering</span>
                                <span className="text-xs text-gray-400 ml-2">2 hours ago</span>
                              </div>
                              <p className="text-sm mt-1">
                                Has anyone looked into the memory leak issue with the image processing service? It seems to be gradually consuming more RAM over time.
                              </p>
                              
                              <div className="mt-3 pl-4 border-l-2 border-secondary">
                                <div className="flex items-start space-x-3 mt-2">
                                  <Avatar className="h-6 w-6">
                                    <AvatarImage src="" />
                                    <AvatarFallback className="bg-accent text-white text-xs">JD</AvatarFallback>
                                  </Avatar>
                                  <div>
                                    <div className="flex items-center">
                                      <span className="font-medium text-sm">Jane Doe</span>
                                      <span className="text-xs text-gray-400 ml-2">1 hour ago</span>
                                    </div>
                                    <p className="text-sm mt-1">
                                      Yes, I've been tracking it. Looks like we're not properly releasing resources in the image transformation pipeline.
                                    </p>
                                  </div>
                                </div>
                                
                                <div className="flex items-start space-x-3 mt-2">
                                  <Avatar className="h-6 w-6">
                                    <AvatarImage src="" />
                                    <AvatarFallback className="bg-primary text-white text-xs">AK</AvatarFallback>
                                  </Avatar>
                                  <div>
                                    <div className="flex items-center">
                                      <span className="font-medium text-sm">Alex Kim</span>
                                      <span className="text-xs text-gray-400 ml-2">45 minutes ago</span>
                                    </div>
                                    <p className="text-sm mt-1">
                                      Great, can you create a ticket for it? Let's prioritize fixing this in the next sprint.
                                    </p>
                                  </div>
                                </div>
                              </div>
                              
                              <div className="mt-2 flex gap-2">
                                <Badge className="bg-secondary bg-opacity-20 text-secondary">Thread</Badge>
                                <Badge className="bg-background-surface text-gray-400">3 messages</Badge>
                              </div>
                            </div>
                            
                            <div>
                              <Tooltip>
                                <Tooltip.Trigger asChild>
                                  <Button variant="ghost" size="sm">
                                    <FaSearch className="h-4 w-4" />
                                  </Button>
                                </Tooltip.Trigger>
                                <Tooltip.Content>
                                  <p>View embedding details</p>
                                </Tooltip.Content>
                              </Tooltip>
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800">
                          <div className="flex items-start space-x-3">
                            <Avatar className="h-8 w-8 mt-1">
                              <AvatarImage src="" />
                              <AvatarFallback className="bg-secondary text-white">MS</AvatarFallback>
                            </Avatar>
                            <div className="flex-1">
                              <div className="flex items-center">
                                <span className="font-medium">Mike Smith</span>
                                <span className="text-xs text-gray-400 ml-2">#general</span>
                                <span className="text-xs text-gray-400 ml-2">1 day ago</span>
                              </div>
                              <p className="text-sm mt-1">
                                Team, I'm excited to announce we've completed the first phase of our new data pipeline project! 🎉 This has been a major effort and I want to thank everyone who contributed.
                              </p>
                              <p className="text-sm mt-2">
                                Key improvements:
                                <br />- 3x faster processing time
                                <br />- Support for new data sources
                                <br />- Improved error handling
                                <br />- Better monitoring
                              </p>
                              
                              <div className="mt-2 flex gap-2">
                                <Badge className="bg-success bg-opacity-20 text-success">Announcement</Badge>
                                <Badge className="bg-background-surface text-gray-400">High Priority</Badge>
                              </div>
                            </div>
                            
                            <div>
                              <Tooltip>
                                <Tooltip.Trigger asChild>
                                  <Button variant="ghost" size="sm">
                                    <FaSearch className="h-4 w-4" />
                                  </Button>
                                </Tooltip.Trigger>
                                <Tooltip.Content>
                                  <p>View embedding details</p>
                                </Tooltip.Content>
                              </Tooltip>
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-background-dark p-4 rounded-lg border border-gray-800">
                          <div className="flex items-start space-x-3">
                            <Avatar className="h-8 w-8 mt-1">
                              <AvatarImage src="" />
                              <AvatarFallback className="bg-accent text-white">JD</AvatarFallback>
                            </Avatar>
                            <div className="flex-1">
                              <div className="flex items-center">
                                <span className="font-medium">Jane Doe</span>
                                <span className="text-xs text-gray-400 ml-2">#product</span>
                                <span className="text-xs text-gray-400 ml-2">3 days ago</span>
                              </div>
                              <p className="text-sm mt-1">
                                Here's the research report on user feedback for the new UI design. Most users found the navigation intuitive, but we still have some issues with the mobile experience.
                              </p>
                              
                              <div className="mt-3 p-3 bg-background-surface rounded-md">
                                <div className="flex items-center text-sm">
                                  <FaSlack className="text-secondary mr-2" />
                                  <span className="font-medium">User Research Report - Q3 2023.pdf</span>
                                </div>
                                <span className="text-xs text-gray-400 mt-1 block">PDF document • 4.2 MB • 12 pages</span>
                              </div>
                              
                              <div className="mt-2 flex gap-2">
                                <Badge className="bg-accent bg-opacity-20 text-accent">File</Badge>
                                <Badge className="bg-background-surface text-gray-400">PDF</Badge>
                              </div>
                            </div>
                            
                            <div>
                              <Tooltip>
                                <Tooltip.Trigger asChild>
                                  <Button variant="ghost" size="sm">
                                    <FaSearch className="h-4 w-4" />
                                  </Button>
                                </Tooltip.Trigger>
                                <Tooltip.Content>
                                  <p>View embedding details</p>
                                </Tooltip.Content>
                              </Tooltip>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="mt-6 flex justify-between items-center">
                        <span className="text-sm text-gray-400">
                          Showing 3 of 1,542 messages
                        </span>
                        <div className="flex items-center space-x-2">
                          <Button variant="outline" size="sm" disabled>
                            Previous
                          </Button>
                          <Button variant="outline" size="sm">
                            Next
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Metadata Inspector
                      </h3>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                          <div className="bg-background-dark p-4 rounded-md border border-gray-800">
                            <h4 className="font-medium mb-3">Message Properties</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">ID:</span>
                                <span className="text-sm font-mono">1637292844.005400</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Channel:</span>
                                <span className="text-sm">#engineering</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">User:</span>
                                <span className="text-sm">U012A3CDE</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Timestamp:</span>
                                <span className="text-sm">2023-08-15T14:23:12Z</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Thread:</span>
                                <span className="text-sm">Yes (3 replies)</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Reactions:</span>
                                <span className="text-sm">4 (👍, 🔍, 💯, 👀)</span>
                              </div>
                            </div>
                          </div>
                          
                          <div className="mt-4 bg-background-dark p-4 rounded-md border border-gray-800">
                            <h4 className="font-medium mb-3">Embedding Properties</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Model:</span>
                                <span className="text-sm">text-embedding-3-large</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Dimensions:</span>
                                <span className="text-sm">1536</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Chunks:</span>
                                <span className="text-sm">2</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Vector ID:</span>
                                <span className="text-sm font-mono">vec_5a72b983</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-400">Created:</span>
                                <span className="text-sm">2023-08-15T14:45:26Z</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div>
                          <div className="bg-background-dark p-4 rounded-md border border-gray-800 h-full">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="font-medium">Chunking Visualization</h4>
                              <Select defaultValue="text">
                                <SelectTrigger className="w-28 h-8 text-xs">
                                  <SelectValue placeholder="View Mode" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="text">Text View</SelectItem>
                                  <SelectItem value="vector">Vector View</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            
                            <div className="space-y-3">
                              <div className="p-3 bg-primary bg-opacity-10 border-l-2 border-primary rounded-r-md">
                                <p className="text-sm">
                                  <span className="text-primary font-medium">Chunk 1:</span> Has anyone looked into the memory leak issue with the image processing service? It seems to be gradually consuming more RAM over time.
                                </p>
                              </div>
                              
                              <div className="p-3 bg-secondary bg-opacity-10 border-l-2 border-secondary rounded-r-md">
                                <p className="text-sm">
                                  <span className="text-secondary font-medium">Chunk 2 (Thread):</span> Yes, I've been tracking it. Looks like we're not properly releasing resources in the image transformation pipeline. Great, can you create a ticket for it? Let's prioritize fixing this in the next sprint.
                                </p>
                              </div>
                            </div>
                            
                            <div className="mt-6">
                              <h4 className="font-medium mb-2">Similar Messages</h4>
                              <div className="text-sm text-gray-400">
                                <ul className="space-y-2">
                                  <li className="flex items-center">
                                    <span className="w-8 text-center">82%</span>
                                    <span>Discussion about resource leaks in backend service</span>
                                  </li>
                                  <li className="flex items-center">
                                    <span className="w-8 text-center">75%</span>
                                    <span>Memory optimization techniques for image processing</span>
                                  </li>
                                  <li className="flex items-center">
                                    <span className="w-8 text-center">68%</span>
                                    <span>Documentation on debugging memory issues</span>
                                  </li>
                                </ul>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="channel-management">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2">
                    <Card className="bg-background-card shadow-card border-gray-800">
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between mb-6">
                          <h3 className="text-lg font-heading font-semibold">
                            Channel Status Dashboard
                          </h3>
                          <Button variant="outline">
                            <FaSync className="mr-2" />
                            Refresh Status
                          </Button>
                        </div>

                        <div className="overflow-x-auto">
                          <Table>
                            <TableHeader>
                              <TableRow className="border-b border-white">
                                <TableHead>Channel</TableHead>
                                <TableHead>Messages</TableHead>
                                <TableHead>Last Sync</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Frequency</TableHead>
                                <TableHead>Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #general
                                </TableCell>
                                <TableCell>5,832</TableCell>
                                <TableCell>10 minutes ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-success bg-opacity-20 text-success">
                                    Active
                                  </Badge>
                                </TableCell>
                                <TableCell>1 hour</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #engineering
                                </TableCell>
                                <TableCell>3,451</TableCell>
                                <TableCell>1 hour ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-success bg-opacity-20 text-success">
                                    Active
                                  </Badge>
                                </TableCell>
                                <TableCell>30 minutes</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #product
                                </TableCell>
                                <TableCell>2,145</TableCell>
                                <TableCell>1 day ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-accent bg-opacity-20 text-accent">
                                    Paused
                                  </Badge>
                                </TableCell>
                                <TableCell>1 day</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #design
                                </TableCell>
                                <TableCell>1,876</TableCell>
                                <TableCell>2 days ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-success bg-opacity-20 text-success">
                                    Active
                                  </Badge>
                                </TableCell>
                                <TableCell>12 hours</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #random
                                </TableCell>
                                <TableCell>4,231</TableCell>
                                <TableCell>3 hours ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-success bg-opacity-20 text-success">
                                    Active
                                  </Badge>
                                </TableCell>
                                <TableCell>6 hours</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                              <TableRow className="border-b border-white">
                                <TableCell className="font-medium">
                                  #announcements
                                </TableCell>
                                <TableCell>562</TableCell>
                                <TableCell>5 days ago</TableCell>
                                <TableCell>
                                  <Badge className="bg-gray-700 text-gray-400">
                                    Archived
                                  </Badge>
                                </TableCell>
                                <TableCell>-</TableCell>
                                <TableCell>
                                  <div className="flex space-x-2">
                                    <Button variant="ghost" size="sm">
                                      <FaSync className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="sm">
                                      <FaCog className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            </TableBody>
                          </Table>
                        </div>

                        <div className="mt-6 flex items-center justify-between">
                          <span className="text-sm text-gray-400">
                            Showing 6 of 12 channels
                          </span>
                          <div className="flex items-center space-x-2">
                            <Button variant="outline" size="sm" disabled>
                              Previous
                            </Button>
                            <Button variant="outline" size="sm">
                              Next
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <div>
                    <Card className="bg-background-card shadow-card border-gray-800">
                      <CardContent className="p-6">
                        <h3 className="text-lg font-heading font-semibold mb-4">
                          Channel Settings
                        </h3>

                        <div className="space-y-6">
                          <div>
                            <Label htmlFor="channel-edit" className="text-sm">
                              Selected Channel
                            </Label>
                            <Select defaultValue="engineering">
                              <SelectTrigger
                                id="channel-edit"
                                className="mt-1 bg-background-dark"
                              >
                                <SelectValue placeholder="Select channel" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="general">#general</SelectItem>
                                <SelectItem value="engineering">#engineering</SelectItem>
                                <SelectItem value="product">#product</SelectItem>
                                <SelectItem value="design">#design</SelectItem>
                                <SelectItem value="random">#random</SelectItem>
                                <SelectItem value="announcements">#announcements</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <Separator className="bg-gray-800" />

                          <div>
                            <Label htmlFor="update-frequency" className="text-sm">
                              Update Frequency
                            </Label>
                            <Select defaultValue="30">
                              <SelectTrigger
                                id="update-frequency"
                                className="mt-1 bg-background-dark"
                              >
                                <SelectValue placeholder="Select frequency" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="15">Every 15 minutes</SelectItem>
                                <SelectItem value="30">Every 30 minutes</SelectItem>
                                <SelectItem value="60">Every hour</SelectItem>
                                <SelectItem value="360">Every 6 hours</SelectItem>
                                <SelectItem value="720">Every 12 hours</SelectItem>
                                <SelectItem value="1440">Every day</SelectItem>
                              </SelectContent>
                            </Select>
                            <p className="text-xs text-gray-400 mt-1">
                              How often to sync new messages
                            </p>
                          </div>

                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="include-threads" className="text-base">
                                Include Threads
                              </Label>
                              <p className="text-xs text-gray-400 mt-1">
                                Process conversation threads
                              </p>
                            </div>
                            <Switch id="include-threads" defaultChecked />
                          </div>

                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="include-emoji" className="text-base">
                                Include Reactions
                              </Label>
                              <p className="text-xs text-gray-400 mt-1">
                                Store emoji reactions as metadata
                              </p>
                            </div>
                            <Switch id="include-emoji" defaultChecked />
                          </div>

                          <div className="flex items-center justify-between">
                            <div>
                              <Label htmlFor="archive-channel" className="text-base">
                                Channel Active
                              </Label>
                              <p className="text-xs text-gray-400 mt-1">
                                Toggle channel processing
                              </p>
                            </div>
                            <Switch id="archive-channel" defaultChecked />
                          </div>

                          <Separator className="bg-gray-800" />

                          <div>
                            <Label className="text-sm mb-2 block">
                              Historical Data Range
                            </Label>
                            <div className="flex items-center justify-between">
                              <Select defaultValue="all">
                                <SelectTrigger className="w-full bg-background-dark">
                                  <SelectValue placeholder="Select range" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="30d">Last 30 days</SelectItem>
                                  <SelectItem value="90d">Last 90 days</SelectItem>
                                  <SelectItem value="180d">Last 6 months</SelectItem>
                                  <SelectItem value="365d">Last year</SelectItem>
                                  <SelectItem value="all">All time</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">
                              Messages to keep in the database
                            </p>
                          </div>

                          <div className="flex justify-end space-x-2 pt-2">
                            <Button variant="outline">Cancel</Button>
                            <Button className="bg-secondary">Save Changes</Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="bg-background-card shadow-card border-gray-800 mt-6">
                      <CardContent className="p-6">
                        <h3 className="text-lg font-heading font-semibold mb-4">
                          Integration Status
                        </h3>

                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <span className="text-sm">API Status</span>
                            <Badge className="bg-success bg-opacity-20 text-success">
                              Connected
                            </Badge>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Rate Limit</span>
                            <span className="text-sm">
                              38/100 <span className="text-gray-400">req/min</span>
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Last Error</span>
                            <span className="text-sm">None</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Token Expiry</span>
                            <span className="text-sm">Never</span>
                          </div>

                          <Separator className="bg-gray-800" />

                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm">API Usage</span>
                              <span className="text-xs text-gray-400">38%</span>
                            </div>
                            <Progress value={38} className="h-1" />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}
