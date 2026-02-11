/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/ArtifactRenderer.tsx
import React from 'react';
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
          <ComponentRenderer key={component.id} component={component} />
        ))}
      </div>
    </div>
  );
};

/**
 * Renders individual layout components
 */
const ComponentRenderer: React.FC<{ component: LayoutComponent }> = ({ component }) => {
  const { component: type, props, width = 'full' } = component;

  const widthClass = {
    full: 'w-full',
    half: 'w-1/2',
    third: 'w-1/3'
  }[width];

  const renderComponent = () => {
    const p = props as any;
    
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