interface ActivityPeriodRowProps {
  label: string;
  activeUsers: number;
  totalRuns: number;
  color: string;
}

export function ActivityPeriodRow({ label, activeUsers, totalRuns, color }: ActivityPeriodRowProps) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-400">{label}</span>
        <span className="text-xs text-gray-500">{activeUsers} users • {totalRuns} runs</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="p-2 bg-background-dark rounded-md text-center">
          <div className="text-xs text-gray-500 mb-1">Users</div>
          <div className="text-lg font-bold" style={{ color }}>{activeUsers}</div>
        </div>
        <div className="p-2 bg-background-dark rounded-md text-center">
          <div className="text-xs text-gray-500 mb-1">Runs</div>
          <div className="text-lg font-bold" style={{ color }}>{totalRuns}</div>
        </div>
      </div>
    </div>
  );
}

