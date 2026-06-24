// src/components/Canvas/Primitives/ChartCard.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useMemo } from 'react';
import { 
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  ScatterChart, Scatter, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

// Color palette for pie chart slices and multi-series
const CHART_COLORS = [
  '#4A90E2', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1'
];

interface ChartCardProps {
  data: any[];
  xKey: string;
  yKey: string;
  title?: string;
  type?: 'line' | 'bar' | 'area' | 'scatter' | 'pie';
  color?: string;
  colorBy?: string;  // For multi-series grouping (e.g., by city)
}

/**
 * Calculates optimal XAxis tick interval to prevent label overcrowding.
 * Shows at most ~12 labels regardless of data size.
 */
const getTickInterval = (dataLength: number): number | undefined => {
  if (dataLength <= 12) return 0; // Show all labels
  return Math.ceil(dataLength / 12) - 1;
};

/**
 * Formats long x-axis labels for readability.
 * Truncates to 12 chars and attempts to show just the date portion for ISO strings.
 */
const formatXLabel = (value: any): string => {
  const str = String(value);
  // If it looks like a date (YYYY-MM-DD...) show just the date
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    return str.slice(0, 10); // "2024-01-15"
  }
  // Truncate long labels
  return str.length > 14 ? str.slice(0, 12) + '…' : str;
};

/**
 * Shared tooltip styling
 */
const tooltipStyle = {
  backgroundColor: 'var(--bg-elevated, #fff)',
  border: '1px solid var(--border-color, #e2e8f0)',
  borderRadius: '8px',
  fontSize: '12px'
};

const ChartCard: React.FC<ChartCardProps> = ({ 
  data, 
  xKey, 
  yKey, 
  title,
  type = 'bar',
  color = '#4A90E2',
  colorBy
}) => {
  // Guard: empty or invalid data
  if (!data || !Array.isArray(data) || data.length === 0) {
    return (
      <div className="space-y-3">
        {title && (
          <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
            {title}
          </h3>
        )}
        <div className="h-[200px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 flex items-center justify-center">
          <p className="text-sm text-slate-400 dark:text-zinc-500">No chart data available</p>
        </div>
      </div>
    );
  }

  // ── Multi-series detection ──
  // If colorBy is specified and the data has that key, group into separate series.
  const seriesGroups = useMemo(() => {
    if (!colorBy || !data[0]?.[colorBy]) return null;
    const groups = new Map<string, any[]>();
    for (const row of data) {
      const key = String(row[colorBy] ?? 'Other');
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(row);
    }
    return groups;
  }, [data, colorBy]);

  const xTickInterval = getTickInterval(data.length);

  // ── Pie Chart ──
  if (type === 'pie') {
    return (
      <div className="space-y-3">
        {title && (
          <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
            {title}
          </h3>
        )}
        <div className="h-[350px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={yKey}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                outerRadius={110}
                innerRadius={50}
                paddingAngle={2}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={true}
              >
                {data.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // ── Scatter Chart ──
  // Uses 'category' type for non-numeric x-axis (e.g., dates as strings)
  if (type === 'scatter') {
    const isNumericX = data.length > 0 && typeof data[0]?.[xKey] === 'number';

    // If we have colorBy groups, render one Scatter per group
    if (seriesGroups && seriesGroups.size > 1) {
      const groupEntries = Array.from(seriesGroups.entries());
      return (
        <div className="space-y-3">
          {title && (
            <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
              {title}
            </h3>
          )}
          <div className="h-[350px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-zinc-700" />
                <XAxis 
                  dataKey={xKey} 
                  type={isNumericX ? 'number' : 'category'}
                  fontSize={11} 
                  stroke="#94a3b8"
                  className="dark:stroke-zinc-500"
                  name={xKey}
                  allowDuplicatedCategory={false}
                  tickFormatter={!isNumericX ? formatXLabel : undefined}
                  interval={!isNumericX ? xTickInterval : undefined}
                  angle={data.length > 10 ? -35 : 0}
                  textAnchor={data.length > 10 ? 'end' : 'middle'}
                  height={data.length > 10 ? 60 : 30}
                />
                <YAxis 
                  dataKey={yKey}
                  type="number"
                  fontSize={11} 
                  stroke="#94a3b8" 
                  className="dark:stroke-zinc-500"
                  name={yKey}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                {groupEntries.map(([group, groupData], idx) => (
                  <Scatter 
                    key={group} 
                    name={group} 
                    data={groupData} 
                    fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      );
    }

    // Single-series scatter
    return (
      <div className="space-y-3">
        {title && (
          <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
            {title}
          </h3>
        )}
        <div className="h-[300px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-zinc-700" />
              <XAxis 
                dataKey={xKey} 
                type={isNumericX ? 'number' : 'category'}
                fontSize={11} 
                stroke="#94a3b8" 
                className="dark:stroke-zinc-500"
                name={xKey}
                allowDuplicatedCategory={false}
                tickFormatter={!isNumericX ? formatXLabel : undefined}
                interval={!isNumericX ? xTickInterval : undefined}
                angle={data.length > 10 ? -35 : 0}
                textAnchor={data.length > 10 ? 'end' : 'middle'}
                height={data.length > 10 ? 60 : 30}
              />
              <YAxis 
                dataKey={yKey}
                type="number"
                fontSize={11} 
                stroke="#94a3b8" 
                className="dark:stroke-zinc-500"
                name={yKey}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Scatter name={yKey} data={data} fill={color} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // ── Multi-series Line / Bar / Area ──
  // When colorBy is present with multiple groups, render one series per group.
  if (seriesGroups && seriesGroups.size > 1 && (type === 'line' || type === 'area')) {
    // For multi-series line/area, we need to pivot the data:
    // each row keyed by xKey, with yKey values per colorBy group as separate columns.
    const pivoted = useMemo(() => {
      const xMap = new Map<string, any>();
      const groupNames = Array.from(seriesGroups.keys());
      for (const [group, rows] of seriesGroups.entries()) {
        for (const row of rows) {
          const xVal = String(row[xKey]);
          if (!xMap.has(xVal)) xMap.set(xVal, { [xKey]: row[xKey] });
          xMap.get(xVal)![group] = row[yKey];
        }
      }
      return { data: Array.from(xMap.values()), groupNames };
    }, [seriesGroups, xKey, yKey]);

    const ChartComp = type === 'line' ? LineChart : AreaChart;

    return (
      <div className="space-y-3">
        {title && (
          <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
            {title}
          </h3>
        )}
        <div className="h-[350px] w-full bg-light-elevated dark:bg-dark-elevated rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <ChartComp data={pivoted.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-zinc-700" />
              <XAxis 
                dataKey={xKey} 
                fontSize={11} 
                stroke="#94a3b8"
                className="dark:stroke-zinc-500"
                tickFormatter={formatXLabel}
                interval={getTickInterval(pivoted.data.length)}
                angle={pivoted.data.length > 10 ? -35 : 0}
                textAnchor={pivoted.data.length > 10 ? 'end' : 'middle'}
                height={pivoted.data.length > 10 ? 60 : 30}
              />
              <YAxis fontSize={11} stroke="#94a3b8" className="dark:stroke-zinc-500" />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {pivoted.groupNames.map((group, idx) => (
                type === 'line' ? (
                  <Line 
                    key={group} 
                    dataKey={group} 
                    stroke={CHART_COLORS[idx % CHART_COLORS.length]} 
                    strokeWidth={2} 
                    dot={{ r: 2 }} 
                    activeDot={{ r: 5 }} 
                  />
                ) : (
                  <Area 
                    key={group} 
                    dataKey={group} 
                    fill={CHART_COLORS[idx % CHART_COLORS.length]} 
                    stroke={CHART_COLORS[idx % CHART_COLORS.length]} 
                    fillOpacity={0.15} 
                  />
                )
              ))}
            </ChartComp>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // ── Standard Single-Series Charts: line, bar, area ──
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
              tickFormatter={formatXLabel}
              interval={xTickInterval}
              angle={data.length > 10 ? -35 : 0}
              textAnchor={data.length > 10 ? 'end' : 'middle'}
              height={data.length > 10 ? 60 : 30}
            />
            <YAxis 
              fontSize={11} 
              stroke="#94a3b8" 
              className="dark:stroke-zinc-500"
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: '11px' }} />
            {type === 'bar' ? (
            <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
            ) : type === 'line' ? (
            <Line dataKey={yKey} stroke={color} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            ) : (
            <Area dataKey={yKey} fill={color} stroke={color} fillOpacity={0.3} />
            )}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ChartCard;