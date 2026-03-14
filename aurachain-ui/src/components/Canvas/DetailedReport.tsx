// aurachain-ui/src/components/Canvas/DetailedReport.tsx
import React, { useEffect } from 'react';
import { ArrowLeft, Download, FileText, Shield, TrendingUp, AlertTriangle, ChevronRight } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';
import type { ReportSection } from '../../types/api';

const DetailedReport: React.FC = () => {
  const {
    setSelectedAgent,
    currentWorkflowId,
    reports,
    isReportLoading,
    fetchReport
  } = useUIStore();

  // Fetch report on mount (lazy — only when user opens this view)
  useEffect(() => {
    if (currentWorkflowId && !reports[currentWorkflowId]) {
      fetchReport(currentWorkflowId);
    }
  }, [currentWorkflowId, reports, fetchReport]);

  const report = currentWorkflowId ? reports[currentWorkflowId] : null;

  // ── Loading State ──
  if (isReportLoading || (!report && currentWorkflowId)) {
    return (
      <div className="h-full flex flex-col bg-light-elevated dark:bg-dark-elevated animate-slide-in">
        <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center">
          <button onClick={() => setSelectedAgent(null)} className="flex items-center text-sm text-slate-500 hover:text-primary-500 transition-colors">
            <ArrowLeft size={16} className="mr-2" /> Back to Workflow
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-10 h-10 border-3 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-500 dark:text-zinc-400">Loading executive report...</p>
          </div>
        </div>
      </div>
    );
  }

  // ── No Report ──
  if (!report) {
    return (
      <div className="h-full flex flex-col bg-light-elevated dark:bg-dark-elevated">
        <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center">
          <button onClick={() => setSelectedAgent(null)} className="flex items-center text-sm text-slate-500 hover:text-primary-500 transition-colors">
            <ArrowLeft size={16} className="mr-2" /> Back to Workflow
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center text-slate-400 dark:text-zinc-500">
            <FileText size={48} className="mx-auto mb-3 opacity-40" />
            <p className="text-sm">No report available yet.</p>
            <p className="text-xs mt-1">The report will appear after agents complete analysis.</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Helpers ──
  const confidenceColor = (score: number) =>
    score >= 0.8 ? 'text-accent-teal' : score >= 0.6 ? 'text-accent-amber' : 'text-red-500';

  const confidenceLabel = (score: number) =>
    score >= 0.8 ? 'High' : score >= 0.6 ? 'Medium' : 'Low';

  const sectionIcon = (title: string) => {
    if (title.toLowerCase().includes('recommend')) return <TrendingUp size={16} />;
    if (title.toLowerCase().includes('risk') || title.toLowerCase().includes('quality')) return <AlertTriangle size={16} />;
    if (title.toLowerCase().includes('confidence')) return <Shield size={16} />;
    return <FileText size={16} />;
  };

  const handleDownload = () => {
    const md = [
      `# ${report.title}`,
      `Generated: ${new Date(report.generated_at).toLocaleString()}`,
      `Overall Confidence: ${Math.round(report.overall_confidence * 100)}%`,
      `Duration: ${(report.total_duration_ms / 1000).toFixed(1)}s`,
      '',
      ...report.sections.map(s =>
        `## ${s.title}\n\n${s.content}\n\n*Source: ${s.agent_source} (${Math.round(s.confidence * 100)}% confidence)*`
      )
    ].join('\n\n');

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${report.workflow_id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ──
  return (
    <div className="h-full flex flex-col bg-light-elevated dark:bg-dark-elevated animate-slide-in">
      {/* Header */}
      <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0">
        <button
          onClick={() => setSelectedAgent(null)}
          className="flex items-center text-sm text-slate-500 hover:text-primary-500 transition-colors"
        >
          <ArrowLeft size={16} className="mr-2" /> Back to Workflow
        </button>
        <button
          onClick={handleDownload}
          className="p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          title="Download as Markdown"
        >
          <Download size={18} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">

        {/* Title + Overall Confidence */}
        <div className="mb-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 rounded-xl">
                <FileText size={24} />
              </div>
              <div>
                <h2 className="text-xl font-heading font-bold text-slate-800 dark:text-zinc-100">
                  {report.title}
                </h2>
                <span className="text-xs text-slate-500 dark:text-zinc-500">
                  {new Date(report.generated_at).toLocaleString()} · {(report.total_duration_ms / 1000).toFixed(1)}s
                </span>
              </div>
            </div>

            {/* Confidence badge */}
            <div className="flex flex-col items-center">
              <div className={`text-2xl font-bold ${confidenceColor(report.overall_confidence)}`}>
                {Math.round(report.overall_confidence * 100)}%
              </div>
              <span className={`text-[10px] font-bold uppercase tracking-wider ${confidenceColor(report.overall_confidence)}`}>
                {confidenceLabel(report.overall_confidence)} Confidence
              </span>
            </div>
          </div>

          {/* Agent pills */}
          <div className="flex flex-wrap gap-1.5 mt-4">
            {report.agents_contributing.map((agent, i) => (
              <span
                key={i}
                className="text-[10px] uppercase font-bold tracking-wider text-slate-500 dark:text-zinc-500 bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded"
              >
                {agent}
              </span>
            ))}
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-5">
          {report.sections.map((section: ReportSection, idx: number) => (
            <div
              key={idx}
              className="bg-slate-50 dark:bg-zinc-800/50 border border-slate-100 dark:border-zinc-700 rounded-xl overflow-hidden"
            >
              {/* Section header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 dark:border-zinc-700/50">
                <div className="flex items-center gap-2.5">
                  <span className="text-primary-500 dark:text-primary-400">
                    {sectionIcon(section.title)}
                  </span>
                  <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-200">
                    {section.title}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-slate-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 rounded-full"
                      style={{ width: `${Math.round(section.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400 dark:text-zinc-500 font-mono">
                    {Math.round(section.confidence * 100)}%
                  </span>
                </div>
              </div>

              {/* Section body */}
              <div className="px-5 py-4">
                <p className="text-sm text-slate-600 dark:text-zinc-300 leading-relaxed whitespace-pre-line">
                  {section.content}
                </p>
                <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-slate-100 dark:border-zinc-700/50">
                  <ChevronRight size={12} className="text-slate-400 dark:text-zinc-600" />
                  <span className="text-[10px] text-slate-400 dark:text-zinc-600 italic">
                    Source: {section.agent_source}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DetailedReport;