/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/DynamicLayout/LayoutGenerator.ts

import { type InferredSchema, type GeneratedLayout, type LayoutComponent } from '../../../types/schema';
import { SchemaInferenceEngine } from './SchemaInference';

/**
 * Layout Generator
 * Maps inferred schema to UI component tree
 */

export class LayoutGenerator {
  
  /**
   * Generate layout from data
   */
  static generate(data: any, agentType?: string): GeneratedLayout {
    // Special handling for known agent types
    if (agentType) {
      const customLayout = this.generateCustomLayout(data, agentType);
      if (customLayout) return customLayout;
    }

    // Infer schema
    const schema = SchemaInferenceEngine.infer(data);
    
    // Generate components based on schema
    const components: LayoutComponent[] = [];

    // Strategy 1: Key-Value Display (Metrics Grid)
    if (SchemaInferenceEngine.isKeyValue(data)) {
      components.push(this.createMetricsGrid(data, schema));
      return { components };
    }

    // Strategy 2: Tabular Data (Data Table)
    if (SchemaInferenceEngine.isTabular(data)) {
      // Check if time series → use chart
      if (SchemaInferenceEngine.isTimeSeries(schema)) {
        components.push(this.createChart(data, schema));
      }
      
      components.push(this.createDataTable(data, schema));
      return { components };
    }

    // Strategy 3: Nested Object (Multiple Components)
    if (schema.type === 'object') {
      const nestedComponents = this.generateNestedLayout(data, schema);
      components.push(...nestedComponents);
      return { components };
    }

    // Fallback: JSON Viewer
    components.push(this.createJsonViewer(data));
    return { components };
  }

  /**
   * Custom layouts for specific agent types
   */
  private static generateCustomLayout(data: any, agentType: string): GeneratedLayout | null {
    const normalized = agentType.toLowerCase().replace(/[_\s-]/g, '');

    switch (normalized) {
      case 'dataharvester':
        return this.generateDataHarvesterLayout(data);
      case 'mctsoptimizer':
        return this.generateOptimizerLayout(data);
      case 'forecaster':
        return this.generateForecasterLayout(data);
      default:
        return null;
    }
  }

  /**
   * Data Harvester Layout
   */
  private static generateDataHarvesterLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];

    // Quality metrics
    if (data.profile) {
      const metrics: Record<string, any> = {
        'Quality Score': `${data.profile.improvement_score || 0}%`,
        'Rows Processed': data.profile.cleaned?.shape?.rows || 0,
        'Columns': data.profile.cleaned?.shape?.cols || 0,
        'Missing Values': Object.values(data.profile.original?.missing_values || {}).reduce((a: any, b: any) => a + b, 0) || 0
      };

      components.push({
        id: 'metrics',
        component: 'MetricsGrid',
        props: { metrics, variant: 'primary' },
        width: 'full',
        order: 1
      });

      // Cleaning operations
      if (data.profile.cleaning_operations?.length > 0) {
        components.push({
          id: 'operations',
          component: 'TextBlock',
          props: {
            title: 'Cleaning Operations',
            items: data.profile.cleaning_operations
          },
          width: 'full',
          order: 2
        });
      }
    }

    return { components };
  }

  /**
   * MCTS Optimizer Layout
   */
  private static generateOptimizerLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];

    // Cost comparison
    if (data.simulation_stats) {
      const metrics: Record<string, any> = {
        'Baseline Cost': `₹${data.simulation_stats.baseline_cost?.toLocaleString() || 0}`,
        'Optimized Cost': `₹${data.simulation_stats.optimized_cost?.toLocaleString() || 0}`,
        'Savings': `${((1 - (data.simulation_stats.optimized_cost / data.simulation_stats.baseline_cost)) * 100).toFixed(1)}%`,
        'Iterations': data.simulation_stats.iterations || 0
      };

      components.push({
        id: 'savings',
        component: 'MetricsGrid',
        props: { metrics, variant: 'success' },
        width: 'full',
        order: 1
      });
    }

    // Recommendation
    if (data.interpretation) {
      components.push({
        id: 'recommendation',
        component: 'TextBlock',
        props: {
          title: 'Recommendation',
          content: data.interpretation,
          variant: 'info'
        },
        width: 'full',
        order: 2
      });
    }

    return { components };
  }

  /**
   * Forecaster Layout
   */
  private static generateForecasterLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];

    // Forecast summary
    if (data.forecasts) {
      const firstMetric = Object.keys(data.forecasts)[0];
      const forecastData = data.forecasts[firstMetric];

      if (Array.isArray(forecastData) && forecastData.length > 0) {
        components.push({
          id: 'forecast-chart',
          component: 'ChartCard',
          props: {
            data: forecastData.map((value: number, index: number) => ({
              period: `Period ${index + 1}`,
              value
            })),
            xKey: 'period',
            yKey: 'value',
            title: `${firstMetric} Forecast`,
            type: 'line'
          },
          width: 'full',
          order: 1
        });
      }

      // Metrics grid for all forecasts
      const metrics: Record<string, any> = {};
      for (const [metric, values] of Object.entries(data.forecasts)) {
        if (Array.isArray(values) && values.length > 0) {
          metrics[metric] = values[0].toFixed(2);
        }
      }

      components.push({
        id: 'forecast-metrics',
        component: 'MetricsGrid',
        props: { metrics },
        width: 'full',
        order: 2
      });
    }

    return { components };
  }

  /**
   * Create Metrics Grid component
   */
  private static createMetricsGrid(data: any, schema: InferredSchema): LayoutComponent {
    const metrics: Record<string, any> = {};

    for (const field of schema.fields) {
      const value = data[field.key];
      if (value !== null && value !== undefined) {
        metrics[field.label || field.key] = this.formatValue(value, field.format);
      }
    }

    return {
      id: 'metrics-grid',
      component: 'MetricsGrid',
      props: { metrics },
      width: 'full',
      order: 1
    };
  }

  /**
   * Create Data Table component
   */
  private static createDataTable(data: any[], schema: InferredSchema): LayoutComponent {
    return {
      id: 'data-table',
      component: 'DataTable',
      props: {
        data,
        columns: schema.fields.map(f => ({
          key: f.key,
          label: f.label || f.key,
          format: f.format
        }))
      },
      width: 'full',
      order: 2
    };
  }

  /**
   * Create Chart component
   */
  private static createChart(data: any[], schema: InferredSchema): LayoutComponent {
    // Find date and numeric fields
    const dateField = schema.fields.find(f => f.type === 'date' || f.format === 'date' || f.format === 'datetime');
    const numericFields = schema.fields.filter(f => f.type === 'number');

    return {
      id: 'time-series-chart',
      component: 'ChartCard',
      props: {
        data,
        xKey: dateField?.key || schema.fields[0]?.key,
        yKey: numericFields[0]?.key || schema.fields[1]?.key,
        title: 'Time Series Data',
        type: 'line'
      },
      width: 'full',
      order: 1
    };
  }

  /**
   * Create JSON Viewer component
   */
  private static createJsonViewer(data: any): LayoutComponent {
    return {
      id: 'json-viewer',
      component: 'JsonViewer',
      props: { data },
      width: 'full',
      order: 99
    };
  }

  /**
   * Generate layout for nested object
   */
  private static generateNestedLayout(data: any, schema: InferredSchema): LayoutComponent[] {
    const components: LayoutComponent[] = [];

    for (const field of schema.fields) {
      const value = data[field.key];

      if (field.type === 'object' && value !== null) {
        // Nested object → Metrics Grid
        if (SchemaInferenceEngine.isKeyValue(value)) {
          components.push({
            id: `nested-${field.key}`,
            component: 'MetricsGrid',
            props: {
              metrics: value,
              title: field.label
            },
            width: 'half',
            order: components.length + 1
          });
        }
      } else if (field.type === 'array' && Array.isArray(value)) {
        // Nested array → Table
        if (SchemaInferenceEngine.isTabular(value)) {
          const arraySchema = SchemaInferenceEngine.infer(value);
          components.push(this.createDataTable(value, arraySchema));
        }
      }
    }

    // If no nested components, show all as metrics
    if (components.length === 0) {
      components.push(this.createMetricsGrid(data, schema));
    }

    return components;
  }

  /**
   * Format value based on format hint
   */
  private static formatValue(value: any, format?: string): string {
    if (value === null || value === undefined) return 'N/A';

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
      case 'datetime':
        return new Date(value).toLocaleDateString();
      default:
        return String(value);
    }
  }
}