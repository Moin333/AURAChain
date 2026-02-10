/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/Primitives/DataTable.tsx
import React, { useState } from 'react';
import { clsx } from 'clsx';
import { ChevronUp, ChevronDown } from 'lucide-react';

interface Column {
  key: string;
  label: string;
  format?: 'currency' | 'percentage' | 'integer' | 'decimal' | 'date' | 'datetime';
}

interface DataTableProps {
  data: any[];
  columns: Column[];
  maxRows?: number;
  sortable?: boolean;
}

const DataTable: React.FC<DataTableProps> = ({ 
  data, 
  columns, 
  maxRows = 10,
  sortable = true 
}) => {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(0);

  const formatValue = (value: any, format?: string): string => {
    if (value === null || value === undefined) return '—';

    switch (format) {
      case 'currency':
        return `₹${Number(value).toLocaleString()}`;
      case 'percentage':
        return `${Number(value).toFixed(1)}%`;
      case 'integer':
        return Number(value).toLocaleString();
      case 'decimal':
        return Number(value).toFixed(2);
      case 'date':
        return new Date(value).toLocaleDateString();
      case 'datetime':
        return new Date(value).toLocaleString();
      default:
        return String(value);
    }
  };

  const handleSort = (key: string) => {
    if (!sortable) return;

    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDirection('asc');
    }
  };

  const processedData = [...data];

  // Sort
  if (sortKey) {
    processedData.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }

  // Paginate
  const totalPages = Math.ceil(processedData.length / maxRows);
  const paginatedData = processedData.slice(
    currentPage * maxRows,
    (currentPage + 1) * maxRows
  );

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-zinc-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-zinc-900">
            <tr>
              {columns.map(col => (
                <th 
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={clsx(
                    'px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-zinc-300 uppercase tracking-wider',
                    sortable && 'cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors'
                  )}
                >
                  <div className="flex items-center gap-2">
                    {col.label}
                    {sortable && sortKey === col.key && (
                      sortDirection === 'asc' 
                        ? <ChevronUp size={14} />
                        : <ChevronDown size={14} />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedData.map((row, idx) => (
              <tr 
                key={idx} 
                className="hover:bg-slate-50 dark:hover:bg-zinc-900/50 transition-colors"
              >
                {columns.map(col => (
                  <td 
                    key={col.key}
                    className="px-4 py-3 text-slate-900 dark:text-zinc-100"
                  >
                    {formatValue(row[col.key], col.format)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-500">
          <div>
            Showing {currentPage * maxRows + 1}–{Math.min((currentPage + 1) * maxRows, data.length)} of {data.length}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="px-3 py-1 rounded bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage === totalPages - 1}
              className="px-3 py-1 rounded bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataTable;