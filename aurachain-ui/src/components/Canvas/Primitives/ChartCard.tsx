// src/components/Canvas/Primitives/ChartCard.tsx
import React from 'react';
import { 
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

interface ChartCardProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  xKey: string;
  yKey: string;
  title?: string;
  type?: 'line' | 'bar' | 'area';
  color?: string;
}

const ChartCard: React.FC<ChartCardProps> = ({ 
  data, 
  xKey, 
  yKey, 
  title,
  type = 'bar',
  color = '#4A90E2'
}) => {
  const ChartComponent = type === 'line' ? LineChart : type === 'area' ? AreaChart : BarChart;

  return (
    <div className="space-y-3">
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
          {title}
        </h3>
      )}
      
      <div className="h-[300px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <ChartComponent data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-zinc-700" />
            <XAxis 
              dataKey={xKey} 
              fontSize={11} 
              stroke="#94a3b8" 
              className="dark:stroke-zinc-500"
            />
            <YAxis 
              fontSize={11} 
              stroke="#94a3b8" 
              className="dark:stroke-zinc-500"
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'var(--bg-elevated)', 
                border: '1px solid var(--border-color)', 
                borderRadius: '8px',
                fontSize: '12px'
              }}
            />
            <Legend 
              wrapperStyle={{ fontSize: '11px' }}
            />
            {type === 'bar' ? (
            <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
            ) : type === 'line' ? (
            <Line dataKey={yKey} stroke={color} />
            ) : (
            <Area dataKey={yKey} fill={color} stroke={color} />
            )}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ChartCard;