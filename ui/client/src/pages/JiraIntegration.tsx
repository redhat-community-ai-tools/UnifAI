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
import { FaJira, FaCog, FaSync, FaDatabase, FaChartBar } from "react-icons/fa";
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

export default function JiraIntegration() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [progress, setProgress] = useState(65);

  const handleConnect = () => {
    setIsConnecting(true);
    setTimeout(() => {
      setIsConnecting(false);
    }, 2000);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Jira Integration"
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
                  <FaCog className="mr-2" />
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
                  value="processing-status"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <FaSync className="mr-2" />
                  Processing Status
                </TabsTrigger>
                <TabsTrigger
                  value="analytics"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <FaChartBar className="mr-2" />
                  Analytics
                </TabsTrigger>
              </TabsList>

              <TabsContent value="add-source">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <div className="flex items-center mb-6">
                        <FaJira className="text-primary text-2xl mr-3" />
                        <h3 className="text-lg font-heading font-semibold">
                          Connect to Jira
                        </h3>
                      </div>

                      <div className="space-y-6">
                        <div>
                          <Label htmlFor="jira-url" className="text-sm">
                            Jira URL
                          </Label>
                          <Input
                            id="jira-url"
                            placeholder="https://your-domain.atlassian.net"
                            className="mt-1 bg-background-dark"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            Your Jira instance URL
                          </p>
                        </div>

                        <div>
                          <Label htmlFor="api-token" className="text-sm">
                            API Token
                          </Label>
                          <Input
                            id="api-token"
                            type="password"
                            placeholder="••••••••••••••••••••"
                            className="mt-1 bg-background-dark"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            Generate an API token from your Atlassian account
                          </p>
                        </div>

                        <div>
                          <Label htmlFor="email" className="text-sm">
                            Email
                          </Label>
                          <Input
                            id="email"
                            type="email"
                            placeholder="your-email@example.com"
                            className="mt-1 bg-background-dark"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            Email associated with your Jira account
                          </p>
                        </div>

                        <Button
                          className="w-full bg-primary"
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
                            <>Connect to Jira</>
                          )}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Project & Issue Configuration
                      </h3>

                      <div className="space-y-6">
                        <div>
                          <Label htmlFor="project-selection" className="text-sm">
                            Select Projects
                          </Label>
                          <Select disabled={!isConnecting}>
                            <SelectTrigger
                              id="project-selection"
                              className="mt-1 bg-background-dark"
                            >
                              <SelectValue placeholder="Select projects..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="eng">Engineering (ENG)</SelectItem>
                              <SelectItem value="prod">Product (PROD)</SelectItem>
                              <SelectItem value="des">Design (DES)</SelectItem>
                              <SelectItem value="mar">Marketing (MAR)</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-gray-400 mt-1">
                            Choose which Jira projects to connect
                          </p>
                        </div>

                        <div>
                          <Label htmlFor="issue-types" className="text-sm">
                            Issue Types
                          </Label>
                          <div className="grid grid-cols-2 gap-2 mt-2">
                            <div className="flex items-center space-x-2">
                              <Switch id="issue-story" defaultChecked disabled={!isConnecting} />
                              <Label htmlFor="issue-story">Story</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Switch id="issue-bug" defaultChecked disabled={!isConnecting} />
                              <Label htmlFor="issue-bug">Bug</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Switch id="issue-task" defaultChecked disabled={!isConnecting} />
                              <Label htmlFor="issue-task">Task</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Switch id="issue-epic" disabled={!isConnecting} />
                              <Label htmlFor="issue-epic">Epic</Label>
                            </div>
                          </div>
                        </div>

                        <div>
                          <Label htmlFor="field-mapping" className="text-sm">
                            Field Mapping
                          </Label>
                          <div className="mt-2 space-y-2">
                            <div className="flex items-center justify-between py-2 border-b border-gray-800">
                              <span className="text-sm">Summary</span>
                              <Badge className="bg-primary bg-opacity-20 text-primary">
                                Mapped
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-800">
                              <span className="text-sm">Description</span>
                              <Badge className="bg-primary bg-opacity-20 text-primary">
                                Mapped
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between py-2 border-b border-gray-800">
                              <span className="text-sm">Comments</span>
                              <Badge className="bg-primary bg-opacity-20 text-primary">
                                Mapped
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between py-2">
                              <span className="text-sm">Custom Fields</span>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={!isConnecting}
                              >
                                Configure
                              </Button>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <div>
                            <Label htmlFor="include-attachments" className="text-base">
                              Include Attachments
                            </Label>
                            <p className="text-xs text-gray-400 mt-1">
                              Extract text from attached files
                            </p>
                          </div>
                          <Switch
                            id="include-attachments"
                            disabled={!isConnecting}
                          />
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
                          Indexed Jira Issues
                        </h3>
                        <div className="flex items-center space-x-2">
                          <Input
                            placeholder="Search issues..."
                            className="w-64 bg-background-dark"
                          />
                          <Button variant="outline">
                            <FaSync className="mr-2" />
                            Refresh
                          </Button>
                        </div>
                      </div>

                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Key</TableHead>
                              <TableHead>Summary</TableHead>
                              <TableHead>Type</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Project</TableHead>
                              <TableHead>Last Updated</TableHead>
                              <TableHead>Vectors</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            <TableRow>
                              <TableCell className="font-medium">
                                ENG-423
                              </TableCell>
                              <TableCell>
                                Implement data visualization component
                              </TableCell>
                              <TableCell>
                                <Badge className="bg-secondary bg-opacity-20 text-secondary">
                                  Story
                                </Badge>
                              </TableCell>
                              <TableCell>In Progress</TableCell>
                              <TableCell>Engineering</TableCell>
                              <TableCell>2 hours ago</TableCell>
                              <TableCell>8</TableCell>
                            </TableRow>
                            <TableRow>
                              <TableCell className="font-medium">
                                ENG-418
                              </TableCell>
                              <TableCell>
                                Fix responsive layout for mobile devices
                              </TableCell>
                              <TableCell>
                                <Badge className="bg-accent bg-opacity-20 text-accent">
                                  Bug
                                </Badge>
                              </TableCell>
                              <TableCell>Done</TableCell>
                              <TableCell>Engineering</TableCell>
                              <TableCell>1 day ago</TableCell>
                              <TableCell>5</TableCell>
                            </TableRow>
                            <TableRow>
                              <TableCell className="font-medium">
                                ENG-405
                              </TableCell>
                              <TableCell>
                                Add authentication to API endpoints
                              </TableCell>
                              <TableCell>
                                <Badge className="bg-secondary bg-opacity-20 text-secondary">
                                  Story
                                </Badge>
                              </TableCell>
                              <TableCell>Done</TableCell>
                              <TableCell>Engineering</TableCell>
                              <TableCell>3 days ago</TableCell>
                              <TableCell>12</TableCell>
                            </TableRow>
                            <TableRow>
                              <TableCell className="font-medium">
                                PROD-56
                              </TableCell>
                              <TableCell>
                                Create user journey map for onboarding flow
                              </TableCell>
                              <TableCell>
                                <Badge className="bg-primary bg-opacity-20 text-primary">
                                  Task
                                </Badge>
                              </TableCell>
                              <TableCell>In Progress</TableCell>
                              <TableCell>Product</TableCell>
                              <TableCell>5 hours ago</TableCell>
                              <TableCell>7</TableCell>
                            </TableRow>
                            <TableRow>
                              <TableCell className="font-medium">
                                ENG-426
                              </TableCell>
                              <TableCell>
                                Update dependencies to latest versions
                              </TableCell>
                              <TableCell>
                                <Badge className="bg-primary bg-opacity-20 text-primary">
                                  Task
                                </Badge>
                              </TableCell>
                              <TableCell>To Do</TableCell>
                              <TableCell>Engineering</TableCell>
                              <TableCell>1 hour ago</TableCell>
                              <TableCell>3</TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                      </div>

                      <div className="flex items-center justify-between mt-4">
                        <span className="text-sm text-gray-400">
                          Showing 5 of 230 issues
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
                        Preview
                      </h3>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="bg-background-dark p-4 rounded-md border border-gray-800">
                          <div className="flex items-center mb-3">
                            <span className="font-medium mr-2">ENG-423</span>
                            <span className="text-gray-400">
                              Implement data visualization component
                            </span>
                          </div>

                          <div className="border-l-2 border-primary pl-3 space-y-2">
                            <div className="bg-background-surface p-2 rounded-md">
                              <p className="text-sm">
                                <span className="text-primary">Chunk 1:</span> We
                                need to implement a data visualization component
                                that can display real-time metrics from our
                                analytics API.
                              </p>
                            </div>
                            <div className="bg-background-surface p-2 rounded-md">
                              <p className="text-sm">
                                <span className="text-primary">Chunk 2:</span>{" "}
                                The component should support multiple chart
                                types: line charts, bar charts, and pie charts.
                                It should be responsive and work on all screen
                                sizes.
                              </p>
                            </div>
                            <div className="bg-background-surface p-2 rounded-md">
                              <p className="text-sm">
                                <span className="text-primary">Comment:</span>{" "}
                                Let's use Chart.js for this implementation, it
                                has all the features we need and good
                                performance.
                              </p>
                            </div>
                          </div>
                        </div>

                        <div>
                          <div className="font-medium mb-3">Vector Embedding</div>
                          <div className="font-mono text-xs text-gray-400 bg-background-dark p-3 rounded-md border border-gray-800 overflow-x-auto max-h-40">
                            [0.024, -0.132, 0.045, 0.081, -0.095, 0.127, 0.036, ...] <br />
                            <span className="text-gray-500 mt-2 block">
                              Displaying first 7 of 1536 dimensions
                            </span>
                          </div>

                          <div className="mt-4">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium">
                                Chunking Settings
                              </span>
                              <Button variant="outline" size="sm">
                                Adjust
                              </Button>
                            </div>
                            <div className="space-y-3">
                              <div className="flex items-center justify-between text-sm">
                                <span>Chunk Size</span>
                                <span>256 tokens</span>
                              </div>
                              <div className="flex items-center justify-between text-sm">
                                <span>Overlap</span>
                                <span>50 tokens</span>
                              </div>
                              <div className="flex items-center justify-between text-sm">
                                <span>Metadata Included</span>
                                <span>Issue ID, Type, Status</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="processing-status">
                <div className="grid grid-cols-1 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-6">
                        Jira Processing Pipeline
                      </h3>

                      <div className="space-y-8">
                        <div className="relative">
                          <div className="absolute left-7 top-0 h-full w-0.5 bg-gray-800"></div>
                          <div className="space-y-8">
                            <div className="relative">
                              <div className="flex items-start">
                                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary bg-opacity-20 z-10">
                                  <Badge className="h-5 w-5 bg-primary p-2">
                                    1
                                  </Badge>
                                </div>
                                <div className="ml-4">
                                  <h4 className="font-medium">Data Extraction</h4>
                                  <p className="text-sm text-gray-400 mt-1">
                                    Fetching issues from Jira API
                                  </p>

                                  <div className="mt-2">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs text-gray-400">
                                        Progress: 100%
                                      </span>
                                      <Badge className="bg-success bg-opacity-20 text-success">
                                        Completed
                                      </Badge>
                                    </div>
                                    <Progress value={100} className="h-1" />
                                  </div>

                                  <div className="text-xs text-gray-400 mt-2">
                                    230 issues extracted from Engineering, Product
                                  </div>
                                </div>
                              </div>
                            </div>

                            <div className="relative">
                              <div className="flex items-start">
                                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-secondary bg-opacity-20 z-10">
                                  <Badge className="h-5 w-5 bg-secondary p-2">
                                    2
                                  </Badge>
                                </div>
                                <div className="ml-4">
                                  <h4 className="font-medium">Text Processing</h4>
                                  <p className="text-sm text-gray-400 mt-1">
                                    Chunking and normalizing text content
                                  </p>

                                  <div className="mt-2">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs text-gray-400">
                                        Progress: 85%
                                      </span>
                                      <Badge className="bg-primary bg-opacity-20 text-primary">
                                        In Progress
                                      </Badge>
                                    </div>
                                    <Progress value={85} className="h-1" />
                                  </div>

                                  <div className="text-xs text-gray-400 mt-2">
                                    Processing rate: 42 issues/minute
                                  </div>
                                </div>
                              </div>
                            </div>

                            <div className="relative">
                              <div className="flex items-start">
                                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent bg-opacity-20 z-10">
                                  <Badge className="h-5 w-5 bg-accent p-2">
                                    3
                                  </Badge>
                                </div>
                                <div className="ml-4">
                                  <h4 className="font-medium">
                                    Embedding Generation
                                  </h4>
                                  <p className="text-sm text-gray-400 mt-1">
                                    Creating vector embeddings
                                  </p>

                                  <div className="mt-2">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs text-gray-400">
                                        Progress: 65%
                                      </span>
                                      <Badge className="bg-primary bg-opacity-20 text-primary">
                                        In Progress
                                      </Badge>
                                    </div>
                                    <Progress value={65} className="h-1" />
                                  </div>

                                  <div className="text-xs text-gray-400 mt-2">
                                    860 embeddings generated so far
                                  </div>
                                </div>
                              </div>
                            </div>

                            <div className="relative">
                              <div className="flex items-start">
                                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-800 z-10">
                                  <Badge className="h-5 w-5 bg-gray-700 p-2">
                                    4
                                  </Badge>
                                </div>
                                <div className="ml-4">
                                  <h4 className="font-medium">
                                    Vector Database Storage
                                  </h4>
                                  <p className="text-sm text-gray-400 mt-1">
                                    Storing embeddings in vector database
                                  </p>

                                  <div className="mt-2">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs text-gray-400">
                                        Progress: 0%
                                      </span>
                                      <Badge className="bg-gray-700 text-gray-400">
                                        Waiting
                                      </Badge>
                                    </div>
                                    <Progress value={0} className="h-1" />
                                  </div>

                                  <div className="text-xs text-gray-400 mt-2">
                                    Waiting for embedding generation to complete
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-4 border-t border-gray-800">
                          <div>
                            <p className="text-sm font-medium">
                              Overall Progress: 65%
                            </p>
                            <p className="text-xs text-gray-400">
                              Estimated time remaining: ~15 minutes
                            </p>
                          </div>
                          <div className="space-x-2">
                            <Button variant="outline">
                              <FaSync className="mr-2" />
                              Refresh Status
                            </Button>
                            <Button variant="outline">Pause Processing</Button>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Processing Logs
                      </h3>

                      <div className="bg-background-dark p-3 rounded-md font-mono text-xs h-60 overflow-y-auto">
                        <div className="text-success">[INFO] 10:42:23 - Starting Jira data processing pipeline</div>
                        <div className="text-gray-400">[INFO] 10:42:24 - Connected to Jira API successfully</div>
                        <div className="text-gray-400">[INFO] 10:42:28 - Fetching issues from Engineering project</div>
                        <div className="text-gray-400">[INFO] 10:42:35 - Retrieved 185 issues from Engineering</div>
                        <div className="text-gray-400">[INFO] 10:42:36 - Fetching issues from Product project</div>
                        <div className="text-gray-400">[INFO] 10:42:40 - Retrieved 45 issues from Product</div>
                        <div className="text-success">[INFO] 10:42:41 - Data extraction complete. Total: 230 issues</div>
                        <div className="text-gray-400">[INFO] 10:42:42 - Starting text processing phase</div>
                        <div className="text-gray-400">[INFO] 10:42:42 - Chunking with size=256, overlap=50</div>
                        <div className="text-gray-400">[INFO] 10:43:30 - Processed 50 issues</div>
                        <div className="text-gray-400">[INFO] 10:44:15 - Processed 100 issues</div>
                        <div className="text-gray-400">[INFO] 10:45:03 - Processed 150 issues</div>
                        <div className="text-error">[WARN] 10:45:18 - Issue ENG-312 has malformed HTML in description</div>
                        <div className="text-gray-400">[INFO] 10:45:19 - Applied fallback text extraction for ENG-312</div>
                        <div className="text-gray-400">[INFO] 10:45:45 - Processed 195 issues</div>
                        <div className="text-gray-400">[INFO] 10:46:30 - Text processing 85% complete</div>
                        <div className="text-gray-400">[INFO] 10:46:31 - Starting embedding generation for processed chunks</div>
                        <div className="text-gray-400">[INFO] 10:46:32 - Using OpenAI text-embedding-3-large model</div>
                        <div className="text-gray-400">[INFO] 10:47:15 - Generated 200 embeddings</div>
                        <div className="text-gray-400">[INFO] 10:48:02 - Generated 400 embeddings</div>
                        <div className="text-gray-400">[INFO] 10:48:48 - Generated 600 embeddings</div>
                        <div className="text-gray-400">[INFO] 10:49:35 - Generated 860 embeddings</div>
                        <div className="text-gray-400">[INFO] 10:49:36 - Embedding generation 65% complete</div>
                      </div>

                      <div className="mt-4 flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 rounded-full bg-success"></div>
                          <span className="text-xs">Info</span>
                          <div className="w-3 h-3 rounded-full bg-accent ml-2"></div>
                          <span className="text-xs">Warning</span>
                          <div className="w-3 h-3 rounded-full bg-error ml-2"></div>
                          <span className="text-xs">Error</span>
                        </div>
                        <Button variant="outline" size="sm">
                          Download Logs
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="analytics">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Data Volume
                      </h3>

                      <div className="h-60">
                        <div className="flex h-full items-end">
                          <div className="flex-1 h-full flex flex-col justify-end items-center">
                            <div className="w-10 bg-primary rounded-t-md" style={{ height: '60%' }}></div>
                            <span className="text-xs mt-2">Engineering</span>
                          </div>
                          <div className="flex-1 h-full flex flex-col justify-end items-center">
                            <div className="w-10 bg-secondary rounded-t-md" style={{ height: '35%' }}></div>
                            <span className="text-xs mt-2">Product</span>
                          </div>
                          <div className="flex-1 h-full flex flex-col justify-end items-center">
                            <div className="w-10 bg-accent rounded-t-md" style={{ height: '15%' }}></div>
                            <span className="text-xs mt-2">Design</span>
                          </div>
                          <div className="flex-1 h-full flex flex-col justify-end items-center">
                            <div className="w-10 bg-success rounded-t-md" style={{ height: '25%' }}></div>
                            <span className="text-xs mt-2">Marketing</span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-gray-400">Total Issues</p>
                          <p className="text-xl font-heading font-semibold">
                            230
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">Total Chunks</p>
                          <p className="text-xl font-heading font-semibold">
                            1,328
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">Total Embeddings</p>
                          <p className="text-xl font-heading font-semibold">
                            1,328
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">
                            Average Chunks/Issue
                          </p>
                          <p className="text-xl font-heading font-semibold">
                            5.8
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Processing Time
                      </h3>

                      <div className="h-60">
                        <div className="flex h-full items-end space-x-2">
                          {[23, 45, 20, 85, 56, 34, 67, 43, 75, 35, 42, 58].map((value, index) => (
                            <div key={index} className="flex-1 h-full flex flex-col justify-end">
                              <div 
                                className="w-full bg-gradient-to-t from-primary to-secondary rounded-t-sm"
                                style={{ height: `${value}%` }}
                              ></div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-gray-400">Average Time</p>
                          <p className="text-xl font-heading font-semibold">
                            185 ms/issue
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">Extraction Time</p>
                          <p className="text-xl font-heading font-semibold">
                            5.2 seconds
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">
                            Embedding Generation
                          </p>
                          <p className="text-xl font-heading font-semibold">
                            4.5 ms/chunk
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-gray-400">Total Time</p>
                          <p className="text-xl font-heading font-semibold">
                            24 minutes
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-background-card shadow-card border-gray-800 md:col-span-2">
                    <CardContent className="p-6">
                      <h3 className="text-lg font-heading font-semibold mb-4">
                        Quality Assessment
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="flex flex-col items-center">
                          <div className="relative w-32 h-32">
                            <svg className="w-full h-full" viewBox="0 0 100 100">
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="#333"
                                strokeWidth="10"
                              />
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="var(--primary)"
                                strokeWidth="10"
                                strokeDasharray={2 * Math.PI * 45}
                                strokeDashoffset={(2 * Math.PI * 45) * (1 - 0.96)}
                                transform="rotate(-90 50 50)"
                              />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                              <span className="text-2xl font-bold">96%</span>
                            </div>
                          </div>
                          <p className="mt-2 font-medium">Text Extraction</p>
                          <p className="text-xs text-gray-400">
                            High quality content extraction
                          </p>
                        </div>

                        <div className="flex flex-col items-center">
                          <div className="relative w-32 h-32">
                            <svg className="w-full h-full" viewBox="0 0 100 100">
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="#333"
                                strokeWidth="10"
                              />
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="var(--secondary)"
                                strokeWidth="10"
                                strokeDasharray={2 * Math.PI * 45}
                                strokeDashoffset={(2 * Math.PI * 45) * (1 - 0.88)}
                                transform="rotate(-90 50 50)"
                              />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                              <span className="text-2xl font-bold">88%</span>
                            </div>
                          </div>
                          <p className="mt-2 font-medium">Chunking Quality</p>
                          <p className="text-xs text-gray-400">
                            Effective semantic boundaries
                          </p>
                        </div>

                        <div className="flex flex-col items-center">
                          <div className="relative w-32 h-32">
                            <svg className="w-full h-full" viewBox="0 0 100 100">
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="#333"
                                strokeWidth="10"
                              />
                              <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="var(--accent)"
                                strokeWidth="10"
                                strokeDasharray={2 * Math.PI * 45}
                                strokeDashoffset={(2 * Math.PI * 45) * (1 - 0.92)}
                                transform="rotate(-90 50 50)"
                              />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                              <span className="text-2xl font-bold">92%</span>
                            </div>
                          </div>
                          <p className="mt-2 font-medium">Metadata Quality</p>
                          <p className="text-xs text-gray-400">
                            Rich context preservation
                          </p>
                        </div>
                      </div>

                      <div className="mt-6 pt-6 border-t border-gray-800">
                        <h4 className="font-medium mb-3">Quality Insights</h4>
                        <ul className="space-y-2 text-sm">
                          <li className="flex items-start">
                            <span className="text-success mr-2">✓</span>
                            <span>Issue content successfully extracted with high fidelity</span>
                          </li>
                          <li className="flex items-start">
                            <span className="text-success mr-2">✓</span>
                            <span>Comments and attachments properly processed</span>
                          </li>
                          <li className="flex items-start">
                            <span className="text-success mr-2">✓</span>
                            <span>Metadata correctly associated with each chunk</span>
                          </li>
                          <li className="flex items-start">
                            <span className="text-accent mr-2">!</span>
                            <span>Some issues have overlong descriptions causing suboptimal chunking</span>
                          </li>
                          <li className="flex items-start">
                            <span className="text-accent mr-2">!</span>
                            <span>Consider adjusting chunk size for better semantic coherence</span>
                          </li>
                        </ul>
                      </div>
                    </CardContent>
                  </Card>
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
