/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/DynamicLayout/SchemaInference.ts

import { type InferredSchema, type SchemaField, type SchemaType } from '../../../types/schema';

/**
 * Schema Inference Engine
 * Analyzes unknown data structures and infers their schema
 */

export class SchemaInferenceEngine {
  
  /**
   * Main entry point: infer schema from any data
   */
  static infer(data: any): InferredSchema {
    if (!data) {
      return {
        type: 'object',
        fields: [],
        confidence: 0
      };
    }

    // Handle arrays
    if (Array.isArray(data)) {
      return this.inferArraySchema(data);
    }

    // Handle objects
    if (typeof data === 'object') {
      return this.inferObjectSchema(data);
    }

    // Primitive types - wrap in object
    return {
      type: 'object',
      fields: [{
        key: 'value',
        type: this.inferPrimitiveType(data),
        label: 'Value'
      }],
      confidence: 1.0
    };
  }

  /**
   * Infer schema from array of items
   */
  private static inferArraySchema(data: any[]): InferredSchema {
    if (data.length === 0) {
      return {
        type: 'array',
        fields: [],
        rowCount: 0,
        confidence: 0.5
      };
    }

    // Sample first few items to infer structure
    const sampleSize = Math.min(10, data.length);
    const samples = data.slice(0, sampleSize);

    // Check if array of primitives or objects
    const firstItem = samples[0];
    
    if (typeof firstItem !== 'object' || firstItem === null) {
      // Array of primitives
      return {
        type: 'array',
        fields: [{
          key: 'value',
          type: this.inferPrimitiveType(firstItem),
          label: 'Value'
        }],
        rowCount: data.length,
        confidence: 0.9
      };
    }

    // Array of objects - merge schemas from samples
    const fields = this.mergeObjectSchemas(samples);

    return {
      type: 'array',
      fields,
      rowCount: data.length,
      confidence: this.calculateConfidence(samples, fields)
    };
  }

  /**
   * Infer schema from single object
   */
  private static inferObjectSchema(data: Record<string, any>): InferredSchema {
    const fields: SchemaField[] = [];

    for (const [key, value] of Object.entries(data)) {
      const field = this.inferFieldSchema(key, value);
      fields.push(field);
    }

    return {
      type: 'object',
      fields,
      confidence: 1.0
    };
  }

  /**
   * Infer schema for a single field
   */
  private static inferFieldSchema(key: string, value: any): SchemaField {
    const type = this.inferType(value);
    const field: SchemaField = {
      key,
      type,
      label: this.formatLabel(key)
    };

    // Add format hints
    if (type === 'number') {
      field.format = this.inferNumberFormat(key, value);
    } else if (type === 'string') {
      field.format = this.inferStringFormat(key, value);
    }

    // Handle nested structures
    if (type === 'array' && Array.isArray(value)) {
      const arraySchema = this.inferArraySchema(value);
      field.itemType = arraySchema.fields[0]?.type || 'string';
      field.itemFields = arraySchema.fields;
    } else if (type === 'object' && value !== null) {
      const objectSchema = this.inferObjectSchema(value);
      field.fields = objectSchema.fields;
    }

    return field;
  }

  /**
   * Infer type of value
   */
  private static inferType(value: any): SchemaType {
    if (value === null || value === undefined) return 'null';
    if (Array.isArray(value)) return 'array';
    if (value instanceof Date) return 'date';
    
    const type = typeof value;
    if (type === 'object') return 'object';
    if (type === 'number') return 'number';
    if (type === 'boolean') return 'boolean';
    return 'string';
  }

  /**
   * Infer primitive type
   */
  private static inferPrimitiveType(value: any): SchemaType {
    const type = this.inferType(value);
    if (type === 'array' || type === 'object') return 'string';
    return type;
  }

  /**
   * Infer number format from key and value
   */
  private static inferNumberFormat(key: string, value: number): 'currency' | 'percentage' | 'integer' | 'decimal' {
    const keyLower = key.toLowerCase();
    
    // Currency indicators
    if (keyLower.includes('cost') || keyLower.includes('price') || keyLower.includes('revenue') || 
        keyLower.includes('amount') || keyLower.includes('value') && value > 100) {
      return 'currency';
    }
    
    // Percentage indicators
    if (keyLower.includes('percent') || keyLower.includes('rate') || keyLower.includes('ratio') ||
        keyLower.includes('score') && value <= 100) {
      return 'percentage';
    }
    
    // Integer vs decimal
    if (Number.isInteger(value)) {
      return 'integer';
    }
    
    return 'decimal';
  }

  /**
   * Infer string format from key and value
   */
  private static inferStringFormat(key: string, value: string): 'date' | 'datetime' | undefined {
    const keyLower = key.toLowerCase();
    
    // Date indicators
    if (keyLower.includes('date') || keyLower.includes('time') || keyLower.includes('timestamp')) {
      // Try to parse as date
      const parsed = new Date(value);
      if (!isNaN(parsed.getTime())) {
        return value.includes('T') || value.includes(':') ? 'datetime' : 'date';
      }
    }
    
    return undefined;
  }

  /**
   * Merge schemas from multiple objects
   */
  private static mergeObjectSchemas(objects: any[]): SchemaField[] {
    const fieldMap = new Map<string, SchemaField>();

    for (const obj of objects) {
      if (typeof obj !== 'object' || obj === null) continue;

      for (const [key, value] of Object.entries(obj)) {
        if (!fieldMap.has(key)) {
          fieldMap.set(key, this.inferFieldSchema(key, value));
        } else {
          // Update existing field (check for nullability, etc.)
          const existing = fieldMap.get(key)!;
          if (value === null || value === undefined) {
            existing.nullable = true;
          }
        }
      }
    }

    return Array.from(fieldMap.values());
  }

  /**
   * Calculate confidence score
   */
  private static calculateConfidence(samples: any[], fields: SchemaField[]): number {
    if (samples.length === 0 || fields.length === 0) return 0;

    let totalScore = 0;
    let totalFields = 0;

    for (const field of fields) {
      let presentCount = 0;
      
      for (const sample of samples) {
        if (sample[field.key] !== undefined && sample[field.key] !== null) {
          presentCount++;
        }
      }

      const fieldScore = presentCount / samples.length;
      totalScore += fieldScore;
      totalFields++;
    }

    return totalFields > 0 ? totalScore / totalFields : 0;
  }

  /**
   * Format key into human-readable label
   */
  private static formatLabel(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .trim();
  }

  /**
   * Check if data is tabular (array of objects with consistent schema)
   */
  static isTabular(data: any): boolean {
    if (!Array.isArray(data) || data.length === 0) return false;
    
    const first = data[0];
    if (typeof first !== 'object' || first === null) return false;

    // Check if all items have similar structure
    const firstKeys = Object.keys(first).sort();
    
    for (let i = 1; i < Math.min(data.length, 10); i++) {
      const item = data[i];
      if (typeof item !== 'object' || item === null) return false;
      
      const itemKeys = Object.keys(item).sort();
      if (itemKeys.length !== firstKeys.length) return false;
      
      // Allow for some key differences (70% match)
      const matchingKeys = itemKeys.filter(k => firstKeys.includes(k));
      if (matchingKeys.length / firstKeys.length < 0.7) return false;
    }

    return true;
  }

  /**
   * Check if data is time series (has date + numeric columns)
   */
  static isTimeSeries(schema: InferredSchema): boolean {
    if (schema.type !== 'array') return false;

    let hasDateField = false;
    let hasNumericField = false;

    for (const field of schema.fields) {
      if (field.type === 'date' || field.format === 'date' || field.format === 'datetime') {
        hasDateField = true;
      }
      if (field.type === 'number') {
        hasNumericField = true;
      }
    }

    return hasDateField && hasNumericField;
  }

  /**
   * Check if data is key-value pairs
   */
  static isKeyValue(data: any): boolean {
    if (typeof data !== 'object' || data === null || Array.isArray(data)) return false;
    
    const entries = Object.entries(data);
    if (entries.length === 0 || entries.length > 20) return false;

    // Check if most values are primitives
    const primitiveCount = entries.filter(([, v]) => 
      typeof v !== 'object' || v === null
    ).length;

    return primitiveCount / entries.length > 0.7;
  }
}