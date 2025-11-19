import React from 'react';

export interface StatItem {
    id: string;
    label: string;
    value: string | number;
}

interface StatsSectionProps {
    stats: StatItem[];
}

export const StatsSection: React.FC<StatsSectionProps> = ({ stats }) => (

    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {stats.map(({ id, label, value }) => (
            <div
                key={id}
                className="flex items-center gap-3 p-4 bg-background-card rounded-2xl shadow-sm"
            >
                <div className="flex justify-between py-2 border-b border-border/30">
                    <span className="text-sm text-muted-foreground">{label}</span>
                    <span className="text-sm text-foreground">{value}</span>
                </div>
            </div>
        ))}
    </div>
);
