// components/DocumentFilters.tsx
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FaSearch } from "react-icons/fa";

interface DocumentFiltersProps {
  fileTypeFilter: string;
  setFileTypeFilter: (value: string) => void;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
}

export function DocumentFilters({fileTypeFilter, setFileTypeFilter, searchQuery, setSearchQuery}: DocumentFiltersProps) {
    
  return (
    <div className="flex items-center space-x-2">
      <Select value={fileTypeFilter} onValueChange={setFileTypeFilter}>
        <SelectTrigger className="w-32 bg-background-dark">
          <SelectValue placeholder="All Types" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          <SelectItem value="pdf">PDF</SelectItem>
          <SelectItem value="docx">Word</SelectItem>
          <SelectItem value="pptx">PowerPoint</SelectItem>
          <SelectItem value="xlsx">Excel</SelectItem>
          <SelectItem value="txt">Text</SelectItem>
        </SelectContent>
      </Select>

      <Input
        placeholder="Search documents..."
        className="w-64 bg-background-dark"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />
    </div>
  );
}
