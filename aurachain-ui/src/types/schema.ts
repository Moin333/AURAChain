/* eslint-disable @typescript-eslint/no-explicit-any */
// src/types/schema.ts

/**
 * Schema inference types for dynamic artifact rendering
 */

export type PrimitiveType = 'string' | 'number' | 'boolean' | 'date' | 'null';
export type ComplexType = 'object' | 'array';
export type SchemaType = PrimitiveType | ComplexType;

export interface SchemaField {
  key: string;
  type: SchemaType;
  format?: 'currency' | 'percentage' | 'integer' | 'decimal' | 'datetime' | 'date';
  nullable?: boolean;
  
  // For arrays
  itemType?: SchemaType;
  itemFields?: SchemaField[];
  
  // For objects
  fields?: SchemaField[];
  
  // Metadata
  label?: string;
  description?: string;
  
  // Statistics (for numbers)
  min?: number;
  max?: number;
  average?: number;
}

export interface InferredSchema {
  type: ComplexType;
  fields: SchemaField[];
  rowCount?: number;
  confidence: number; // 0-1 score
}

export type ComponentType = 
  | 'MetricsGrid'
  | 'DataTable'
  | 'ChartCard'
  | 'TextBlock'
  | 'JsonViewer'
  | 'Alert'
  | 'ProgressBar';

export interface LayoutComponent {
  id: string;
  component: ComponentType;
  props: Record<string, any>;
  width?: 'full' | 'half' | 'third';
  order?: number;
}

export interface GeneratedLayout {
  components: LayoutComponent[];
  title?: string;
  description?: string;
}