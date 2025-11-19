import { Card, CardContent } from "@/components/ui/card";
import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { FaChevronDown, FaChevronRight } from "react-icons/fa";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FaInfoCircle } from "react-icons/fa";
import { Badge } from "@/components/ui/badge";


interface ProcessingOptionsProps {
  className?: string;
}

interface ProcessingSettings {
  autoProcess: boolean;
  extractMetadata: boolean;
  ocrEnabled: boolean;
}

export const ProcessingOptions: React.FC<ProcessingOptionsProps> = ({ className }) => {
  const [showProcessingOptions, setShowProcessingOptions] = useState(false);
  const [settings, setSettings] = useState<ProcessingSettings>({
    autoProcess: true,
    extractMetadata: true,
    ocrEnabled: false,
  });

  const handleSettingChange = (key: keyof ProcessingSettings, value: boolean) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className={className}>
      <div
        className="flex items-center space-x-2 cursor-pointer text-primary text-sm font-semibold mt-4"
        onClick={() => setShowProcessingOptions((prev) => !prev)}
      >
        {showProcessingOptions ? (
          <FaChevronDown className="transition-transform duration-200" />
        ) : (
          <FaChevronRight className="transition-transform duration-200" />
        )}
        <span>Processing Options</span>
      </div>

      {showProcessingOptions && (
        <div className="space-y-4 mt-4">
          {/* Processing Tips */}
          <Alert className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
            <FaInfoCircle className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertDescription className="text-blue-800 dark:text-blue-200">
              <strong>Processing Tips:</strong>
              <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                <li>Auto-processing starts embedding immediately after upload</li>
                <li>Metadata extraction improves search and filtering capabilities</li>
                <li>OCR is coming soon for extracting text from image-based documents</li>
              </ul>
            </AlertDescription>
          </Alert>

          <Card className="bg-background-card shadow-card border-gray-800 w-full">
            <CardContent className="p-6 space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <Label htmlFor="auto-process" className="text-base font-medium">
                    Auto-Process Files
                  </Label>
                  <p className="text-xs text-gray-400 mt-1">
                    Automatically start processing after upload
                  </p>
                </div>
                <Switch 
                  id="auto-process" 
                  checked={settings.autoProcess}
                  onCheckedChange={(checked) => handleSettingChange('autoProcess', checked)}
                  className="ml-4"
                />
              </div>

              <Separator className="bg-gray-800" />

              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <Label htmlFor="extract-metadata" className="text-base font-medium">
                    Extract Metadata
                  </Label>
                  <p className="text-xs text-gray-400 mt-1">
                    Extract file properties as metadata
                  </p>
                </div>
                <Switch 
                  id="extract-metadata" 
                  checked={settings.extractMetadata}
                  onCheckedChange={(checked) => handleSettingChange('extractMetadata', checked)}
                  className="ml-4"
                />
              </div>

              <Separator className="bg-gray-800" />

              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="ocr-enabled" className="text-base font-medium">
                      Enable OCR
                    </Label>
                    <Badge variant="secondary" className="text-xs px-2 py-0">Soon</Badge>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Extract text from images within documents
                  </p>
                </div>
                <Switch 
                  id="ocr-enabled" 
                  checked={settings.ocrEnabled}
                  onCheckedChange={(checked) => handleSettingChange('ocrEnabled', checked)}
                  disabled={true}
                  className="ml-4 opacity-50"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};