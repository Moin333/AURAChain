/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/ArtifactRenderer.tsx
import React, { useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { normalizeAgentName } from '../../store/uiStore';
import { LayoutGenerator } from './DynamicLayout/LayoutGenerator';
import { 
  MetricsGrid, 
  DataTable, 
  ChartCard, 
  JsonViewer, 
  TextBlock, 
  AlertBanner 
} from './Primitives';
import { type LayoutComponent } from '../../types/schema';

interface ArtifactRendererProps {
  agentType: string;
  data: any;
}

const ArtifactRenderer: React.FC<ArtifactRendererProps> = ({ agentType, data }) => {
  const normalizedType = normalizeAgentName(agentType);

  // Handle errors
  if (!data || (data.error && typeof data.error === 'string')) {
    return (
      <AlertBanner
        type="error"
        title="Execution Failed"
        message={data?.error || "The agent could not complete the task. Please check backend logs."}
      />
    );
  }

  // Handle empty data
  if (Object.keys(data).length === 0) {
    return (
      <AlertBanner
        type="info"
        title="No Data"
        message="This agent completed successfully but returned no data."
      />
    );
  }

  console.log('🎨 Rendering artifact:', {
    agentType,
    normalizedType,
    hasData: !!data,
    dataKeys: Object.keys(data)
  });

  // Generate layout using dynamic system
  const layout = LayoutGenerator.generate(data, normalizedType);

  // Render components from layout
  return (
    <div className="space-y-6 animate-fade-in">
      {layout.title && (
        <div>
          <h2 className="text-xl font-bold text-slate-800 dark:text-zinc-100">
            {layout.title}
          </h2>
          {layout.description && (
            <p className="text-sm text-slate-600 dark:text-zinc-400 mt-1">
              {layout.description}
            </p>
          )}
        </div>
      )}

      <div className="space-y-4">
        {layout.components.map((component) => (
          <ComponentRenderer key={component.id} component={component} agentData={data}/>
        ))}
      </div>
    </div>
  );
};

/*
Order Manager Approval Button
*/

const OrderApprovalActions: React.FC<{ data: any }> = ({ data }) => {
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');

  const qty = data?.optimal_action?.order_quantity ?? data?.order_quantity ?? 0;
  const cost = data?.simulation_stats?.optimized_cost ?? data?.estimated_cost ?? 0;

  if (status === 'approved') {
    return (
      <AlertBanner
        type="success"
        title="Order Approved"
        message={`Purchase order for ${Number(qty).toLocaleString()} units (₹${Number(cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}) has been sent to the vendor.`}
      />
    );
  }

  if (status === 'rejected') {
    return (
      <AlertBanner
        type="error"
        title="Order Rejected"
        message="The purchase order has been rejected and will not be processed."
      />
    );
  }

  return (
    <div className="flex gap-3 pt-1">
      <button
        onClick={() => setStatus('approved')}
        className="flex-1 flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-all shadow-lg shadow-primary-500/20 text-sm"
      >
        <CheckCircle2 size={16} />
        Approve & Send Order
      </button>
      <button
        onClick={() => setStatus('rejected')}
        className="flex-1 flex items-center justify-center gap-2 bg-light-elevated dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-300 hover:bg-red-50 dark:hover:bg-red-900/10 hover:border-red-300 dark:hover:border-red-800 hover:text-red-600 dark:hover:text-red-400 py-3 rounded-xl font-medium transition-all text-sm"
      >
        <XCircle size={16} />
        Reject
      </button>
    </div>
  );
};


/**
 * Renders individual layout components
 */
const ComponentRenderer: React.FC<{ component: LayoutComponent; agentData: any }> = ({ component, agentData }) => {
  const { component: type, props, width = 'full' } = component;

  const widthClass = {
    full: 'w-full',
    half: 'w-1/2',
    third: 'w-1/3'
  }[width];

  const renderComponent = () => {
    const p = props as any;

    if (type === 'TextBlock' && p.content === '__ORDER_APPROVAL_ACTIONS__') {
      return <OrderApprovalActions data={agentData}/>;
    }
    
    try {
      switch (type) {
        case 'MetricsGrid':
          return <MetricsGrid {...p} />;
        
        case 'DataTable':
          return <DataTable {...p} />;
        
        case 'ChartCard':
          return <ChartCard {...p} />;
        
        case 'TextBlock':
          return <TextBlock {...p} />;
        
        case 'JsonViewer':
          return <JsonViewer {...p} />;
        
        case 'Alert':
          return <AlertBanner {...p} />;
        
        default:
          console.warn(`Unknown component type: ${type}`);
          return <JsonViewer data={props} title={`Unknown: ${type}`} />;
      }
    } catch (error) {
      console.error(`Error rendering ${type}:`, error);
      return (
        <AlertBanner
          type="error"
          title={`Failed to render ${type}`}
          message={error instanceof Error ? error.message : 'Unknown error'}
        />
      );
    }
  };

  return (
    <div className={widthClass}>
      {renderComponent()}
    </div>
  );
};

export default ArtifactRenderer;