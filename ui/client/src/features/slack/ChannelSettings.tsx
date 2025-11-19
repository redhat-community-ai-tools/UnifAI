import React from 'react';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export interface ChannelSettingsData {
  dateRange: string;
  includeThreads: boolean;
  processFileContent: boolean;
}

export interface ChannelSettingsProps {
  channelId: string;
  channelName: string;
  settings: ChannelSettingsData;
  onSettingsChange: (channelId: string, settings: ChannelSettingsData) => void;
}

export const defaultChannelSettings: ChannelSettingsData = {
  dateRange: '180d',
  includeThreads: true,
  processFileContent: false,
};

export function ChannelSettings({ 
  channelId, 
  channelName, 
  settings, 
  onSettingsChange 
}: ChannelSettingsProps) {
  const updateSetting = <K extends keyof ChannelSettingsData>(
    key: K, 
    value: ChannelSettingsData[K]
  ) => {
    onSettingsChange(channelId, { ...settings, [key]: value });
  };

  return (
    <div className="bg-background-card border border-gray-800 rounded-lg p-4 space-y-4">
      <h4 className="font-medium text-sm text-foreground">
        Settings for{' '}
        <span className="inline-block px-3 py-1 bg-blue-500/20 border border-blue-500/40 rounded-md text-blue-400 font-bold text-base">
          #{channelName}
        </span>
      </h4>
      
      {/* Date Range */}
      <div>
        <Label htmlFor={`date-range-${channelId}`} className="text-sm">
          Date Range
        </Label>
        <Select 
          value={settings.dateRange} 
          onValueChange={(value) => updateSetting('dateRange', value)}
        >
          <SelectTrigger
            id={`date-range-${channelId}`}
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

      {/* Include Threads - Disabled for now */}
      <div className="flex items-center justify-between pt-1 opacity-50 cursor-not-allowed">
        <div>
          <div className="flex items-center space-x-2">
            <Label htmlFor={`include-threads-${channelId}`} className="text-base">
              Include Threads
            </Label>
            <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 font-medium">
              Disabled
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Process conversation threads
          </p>
        </div>
        <Switch 
          id={`include-threads-${channelId}`} 
          checked={settings.includeThreads}
          disabled
        />
      </div>

      {/* Process File Content - Disabled for now */}
      <div className="flex items-start justify-between opacity-50 cursor-not-allowed">
        <div>
          <div className="flex items-center space-x-2">
            <Label htmlFor={`include-files-${channelId}`} className="text-base">
              Process File Content
            </Label>
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary text-white font-medium">
              Soon
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Extract text from shared files
          </p>
        </div>
        <div className="flex items-center space-x-2 pt-1">
          <Switch 
            id={`include-files-${channelId}`} 
            checked={settings.processFileContent}
            disabled 
          />
        </div>
      </div>
    </div>
  );
} 