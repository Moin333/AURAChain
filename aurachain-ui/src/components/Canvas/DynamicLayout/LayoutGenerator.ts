/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/DynamicLayout/LayoutGenerator.ts

import { type InferredSchema, type GeneratedLayout, type LayoutComponent } from '../../../types/schema';
import { SchemaInferenceEngine } from './SchemaInference';

export class LayoutGenerator {

  static generate(data: any, agentType?: string): GeneratedLayout {
    if (agentType) {
      const customLayout = this.generateCustomLayout(data, agentType);
      if (customLayout) return customLayout;
    }

    const schema = SchemaInferenceEngine.infer(data);
    const components: LayoutComponent[] = [];

    if (SchemaInferenceEngine.isKeyValue(data)) {
      components.push(this.createMetricsGrid(data, schema));
      return { components };
    }

    if (SchemaInferenceEngine.isTabular(data)) {
      if (SchemaInferenceEngine.isTimeSeries(schema)) {
        components.push(this.createChart(data, schema));
      }
      components.push(this.createDataTable(data, schema));
      return { components };
    }

    if (schema.type === 'object') {
      const nestedComponents = this.generateNestedLayout(data, schema);
      components.push(...nestedComponents);
      return { components };
    }

    components.push(this.createJsonViewer(data));
    return { components };
  }

  // ─────────────────────────────────────────────
  // CUSTOM LAYOUT ROUTER
  // ─────────────────────────────────────────────
  private static generateCustomLayout(data: any, agentType: string): GeneratedLayout | null {
    const normalized = agentType.toLowerCase().replace(/[_\s-]/g, '');

    switch (normalized) {
      case 'dataharvester':   return this.generateDataHarvesterLayout(data);
      case 'trendanalyst':    return this.generateTrendAnalystLayout(data);
      case 'forecaster':      return this.generateForecasterLayout(data);
      case 'mctsoptimizer':   return this.generateOptimizerLayout(data);
      case 'ordermanager':    return this.generateOrderManagerLayout(data);
      case 'notifier':        return this.generateNotifierLayout(data);
      case 'visualizer':      return this.generateVisualizerLayout(data);
      default:                return null;
    }
  }

  // ─────────────────────────────────────────────
  // DATA HARVESTER
  // ─────────────────────────────────────────────
  private static generateDataHarvesterLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];
    const profile = data?.profile || {};
    const cleaned = profile?.cleaned || {};
    const original = profile?.original || {};

    // 🔥 FIX: Use correct nested paths for shape
    const rows = cleaned?.shape?.rows ?? cleaned?.shape?.[0] ?? 0;
    const cols = cleaned?.shape?.cols ?? cleaned?.shape?.[1] ?? cleaned?.shape?.columns ?? 0;

    // Count all missing values across columns
    const missingValues = Object.values(original?.missing_values ?? {})
      .reduce((acc: number, val: any) => acc + Number(val), 0);

    const metrics: Record<string, any> = {
      'Quality Score': `${profile?.improvement_score ?? 0}%`,
      'Rows Processed': rows.toLocaleString(),
      'Columns': cols,
      'Missing Values Fixed': missingValues
    };

    components.push({
      id: 'dh-metrics',
      component: 'MetricsGrid',
      props: { metrics, variant: 'primary' },
      width: 'full',
      order: 1
    });

    // Cleaning operations list
    const ops: string[] = profile?.cleaning_operations ?? [];
    if (ops.length > 0) {
      components.push({
        id: 'dh-ops',
        component: 'TextBlock',
        props: { title: 'Cleaning Operations', items: ops, variant: 'info' },
        width: 'full',
        order: 2
      });
    }

    // Column info table
    const dtypes = cleaned?.dtypes ?? {};
    if (Object.keys(dtypes).length > 0) {
      const tableData = Object.entries(dtypes).map(([col, dtype]) => ({
        column: col,
        type: String(dtype),
        missing: String(original?.missing_values?.[col] ?? 0)
      }));

      components.push({
        id: 'dh-columns',
        component: 'DataTable',
        props: {
          data: tableData,
          columns: [
            { key: 'column', label: 'Column' },
            { key: 'type', label: 'Data Type' },
            { key: 'missing', label: 'Missing (original)' }
          ],
          maxRows: 10,
          sortable: false
        },
        width: 'full',
        order: 3
      });
    }

    return { components };
  }

  // ─────────────────────────────────────────────
  // TREND ANALYST - 🔥 FIX [object Object]
  // ─────────────────────────────────────────────
  private static generateTrendAnalystLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];
    const analysis = data?.analysis ?? {};
    const insights = data?.insights  ?? {};
    const metadata = data?.metadata  ?? {};

    // 1. Metadata bar
    const metaMetrics: Record<string, string> = {};
    if (metadata.data_points_analyzed)
      metaMetrics['Data Points'] = Number(metadata.data_points_analyzed).toLocaleString();
    if (metadata.analysis_date) {
      const d = new Date(metadata.analysis_date);
      metaMetrics['Analysed At'] = isNaN(d.getTime()) ? String(metadata.analysis_date)
        : d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
    if (insights.market_sentiment)
      metaMetrics['Market Sentiment'] =
        String(insights.market_sentiment).charAt(0).toUpperCase() + String(insights.market_sentiment).slice(1);

    if (Object.keys(metaMetrics).length > 0) {
      components.push({
        id: 'ta-meta', component: 'MetricsGrid',
        props: { metrics: metaMetrics, columns: 4 },
        width: 'full', order: 1
      });
    }

    // 2. Internal trends — flatten each metric into readable cards
    const internalTrends = analysis?.internal_trends ?? {};
    const internalMetrics: Record<string, string> = {};
    for (const [metric, trend] of Object.entries(internalTrends)) {
      const t     = trend as Record<string, any>;
      const dir   = String(t?.trend_direction ?? 'N/A');
      const vol   = String(t?.volatility ?? 'N/A');
      const growth = t?.statistics?.growth_rate_pct;
      const label = this.formatLabel(metric);
      internalMetrics[`${label} — Trend`]      = dir.charAt(0).toUpperCase() + dir.slice(1);
      internalMetrics[`${label} — Volatility`] = vol.charAt(0).toUpperCase() + vol.slice(1);
      if (growth !== undefined)
        internalMetrics[`${label} — Growth`]    = `${Number(growth).toFixed(1)}%`;
      if (t?.anomalies_detected !== undefined)
        internalMetrics[`${label} — Anomalies`] = String(t.anomalies_detected);
    }
    if (Object.keys(internalMetrics).length > 0) {
      components.push({
        id: 'ta-internal', component: 'MetricsGrid',
        props: { metrics: internalMetrics, title: '📊 Internal Trends', columns: 4 },
        width: 'full', order: 2
      });
    }

    // 3. External trends
    const externalTrends = analysis?.external_trends ?? {};
    const externalMetrics: Record<string, string> = {};
    for (const [keyword, trend] of Object.entries(externalTrends)) {
      const t = trend as Record<string, any>;
      externalMetrics[`${keyword} — Interest`] = `${t?.current_interest ?? 0} / 100`;
      externalMetrics[`${keyword} — Peak`]     = String(t?.peak_interest ?? 0);
      externalMetrics[`${keyword} — Change`]   = `${Number(t?.change_percentage ?? 0).toFixed(1)}%`;
      const tr = String(t?.trend ?? 'N/A');
      externalMetrics[`${keyword} — Trend`]    = tr.charAt(0).toUpperCase() + tr.slice(1);
    }
    if (Object.keys(externalMetrics).length > 0) {
      components.push({
        id: 'ta-external', component: 'MetricsGrid',
        props: { metrics: externalMetrics, title: '🌐 External Market Trends', columns: 4 },
        width: 'full', order: 3
      });
    }

    // 4. Key Findings
    const keyFindings: string[] = insights?.key_findings ?? [];
    if (keyFindings.length > 0) {
      components.push({
        id: 'ta-findings', component: 'TextBlock',
        props: { title: '💡 Key Findings', items: keyFindings, variant: 'info' },
        width: 'full', order: 4
      });
    }

    // 5. Opportunities
    const opps: any[] = insights?.opportunities ?? [];
    if (opps.length > 0) {
      components.push({
        id: 'ta-opps', component: 'TextBlock',
        props: {
          title: '🚀 Opportunities',
          items: opps.map((o: any) =>
            `[${Math.round((o.confidence ?? 0) * 100)}% confidence] ${o.message ?? ''}`),
          variant: 'success'
        },
        width: 'full', order: 5
      });
    }

    // 6. Risks
    const risks: any[] = insights?.risks ?? [];
    if (risks.length > 0) {
      components.push({
        id: 'ta-risks', component: 'TextBlock',
        props: {
          title: '⚠️ Risks',
          items: risks.map((r: any) =>
            `[${Math.round((r.confidence ?? 0) * 100)}% confidence] ${r.message ?? ''}`),
          variant: 'warning'
        },
        width: 'full', order: 6
      });
    }

    // 7. Recommendations
    const recs: string[] = insights?.recommendations ?? [];
    if (recs.length > 0) {
      components.push({
        id: 'ta-recs', component: 'TextBlock',
        props: { title: '📋 Recommendations', items: recs, variant: 'default' },
        width: 'full', order: 7
      });
    }

    return { components };
  }

  // ─────────────────────────────────────────────
  // FORECASTER - 🔥 FIX blank content
  // ─────────────────────────────────────────────
  private static generateForecasterLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];
    const forecasts      = data?.forecasts     ?? {};
    const forecastKeys   = Object.keys(forecasts);
    const metadata       = data?.metadata      ?? {};
    const interpretation = data?.interpretation ?? '';

    // 1. Model config metrics
    const modelMetrics: Record<string, string> = {};
    if (metadata.model)                     modelMetrics['Model']            = String(metadata.model);
    if (data.forecast_periods)              modelMetrics['Forecast Periods'] = String(data.forecast_periods);
    if (metadata.date_column)               modelMetrics['Date Column']      = String(metadata.date_column);
    if (metadata.includes_holidays != null) modelMetrics['Holidays']         = metadata.includes_holidays ? 'Included' : 'Not included';
    if (Object.keys(modelMetrics).length > 0) {
      components.push({
        id: 'fc-model', component: 'MetricsGrid',
        props: { metrics: modelMetrics, title: '🤖 Model Configuration' },
        width: 'full', order: 1
      });
    }

    // 2. One area chart + stats card per forecast metric
    forecastKeys.forEach((metric, idx) => {
      const forecastObj = forecasts[metric] ?? {};

      // ── The actual array lives at forecastObj.predictions ──
      const predictions: any[] = forecastObj?.predictions ?? [];
      if (predictions.length === 0) return;

      // Build chart-friendly data
      const chartData = predictions.slice(0, 30).map((v: any, i: number) => {
        if (typeof v === 'object' && v !== null) {
          const raw   = v.ds ?? v.date ?? v.period;
          const label = raw
            ? new Date(raw).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            : `Day ${i + 1}`;
          const yVal  = v.yhat ?? v.value ?? v.forecast ?? v.predicted ?? 0;
          return { period: label, value: Number(Number(yVal).toFixed(2)) };
        }
        return { period: `Day ${i + 1}`, value: Number(Number(v).toFixed(2)) };
      });

      components.push({
        id: `fc-chart-${idx}`, component: 'ChartCard',
        props: {
          data:  chartData,
          xKey:  'period',
          yKey:  'value',
          title: `${this.formatLabel(metric)} — 30-Day Forecast`,
          type:  'area',
          color: idx === 0 ? '#4A90E2' : '#10b981'
        },
        width: 'full', order: idx * 3 + 2
      });

      // Stats for this metric
      const fcMetrics: Record<string, string> = {};
      if (forecastObj.confidence_score != null)
        fcMetrics['Confidence Score'] = `${(Number(forecastObj.confidence_score) * 100).toFixed(0)}%`;

      const perf = forecastObj?.metrics ?? {};
      for (const [k, v] of Object.entries(perf)) {
        if (typeof v === 'number') fcMetrics[this.formatLabel(k)] = Number(v).toFixed(2);
      }

      const first = chartData[0]?.value;
      const last  = chartData[chartData.length - 1]?.value;
      if (first != null) fcMetrics['Day 1 Forecast']  = String(first);
      if (last  != null) fcMetrics['Day 30 Forecast'] = String(last);

      if (Object.keys(fcMetrics).length > 0) {
        components.push({
          id: `fc-stats-${idx}`, component: 'MetricsGrid',
          props: { metrics: fcMetrics, title: `${this.formatLabel(metric)} — Stats` },
          width: 'full', order: idx * 3 + 3
        });
      }
    });

    // 3. Interpretation text (strip markdown **)
    if (typeof interpretation === 'string' && interpretation.trim().length > 0) {
      components.push({
        id: 'fc-interp', component: 'TextBlock',
        props: {
          title: '📝 Forecast Interpretation',
          content: interpretation.replace(/\*\*/g, '').trim(),
          variant: 'info'
        },
        width: 'full', order: 99
      });
    }

    if (components.length === 0) {
      components.push(this.createJsonViewer(data, 'Forecast Data'));
    }

    return { components };
  }


  // ─────────────────────────────────────────────
  // MCTS OPTIMIZER (already working - keep)
  // ─────────────────────────────────────────────
  private static generateOptimizerLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];
    const stats = data?.simulation_stats ?? {};

    const baseline = stats.baseline_cost ?? 0;
    const optimized = stats.optimized_cost ?? 0;
    const savingsPct = baseline > 0
      ? ((1 - optimized / baseline) * 100).toFixed(1)
      : '0.0';

    const metrics: Record<string, string> = {
      'Baseline Cost':   `₹${Number(baseline).toLocaleString()}`,
      'Optimized Cost':  `₹${Number(optimized).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      'Savings':         `${savingsPct}%`,
      'Iterations':      (stats.iterations ?? 0).toLocaleString()
    };

    components.push({
      id: 'mcts-metrics',
      component: 'MetricsGrid',
      props: { metrics, variant: 'success' },
      width: 'full',
      order: 1
    });

    const interpretation = data?.interpretation ?? '';
    if (typeof interpretation === 'string' && interpretation.length > 0) {
      components.push({
        id: 'mcts-rec',
        component: 'TextBlock',
        props: { title: 'Recommendation', content: interpretation, variant: 'info' },
        width: 'full',
        order: 2
      });
    }

    return { components };
  }

  // ─────────────────────────────────────────────
  // ORDER MANAGER - 🔥 FIX: Human-in-the-loop
  // ─────────────────────────────────────────────
  private static generateOrderManagerLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];

    // Extract only structured fields - IGNORE the LLM plan text
    const qty = data?.optimal_action?.order_quantity
      ?? data?.order_quantity
      ?? data?.quantity
      ?? 0;

    const optimizedCost = data?.simulation_stats?.optimized_cost
      ?? data?.estimated_cost
      ?? data?.total_cost
      ?? 0;

    const orderMetrics: Record<string, string> = {
      'Order Quantity': `${Number(qty).toLocaleString()} units`,
      'Estimated Cost': `₹${Number(optimizedCost).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      'Vendor':         data?.vendor ?? 'Rajesh Electronics',
      'Status':         data?.status ?? 'Draft'
    };

    components.push({
      id: 'om-metrics',
      component: 'MetricsGrid',
      props: { metrics: orderMetrics, variant: 'warning', title: 'Order Summary' },
      width: 'full',
      order: 1
    });

    // Human-in-the-loop approval block
    components.push({
      id: 'om-approval',
      component: 'Alert',
      props: {
        type: 'warning',
        title: 'Approval Required',
        message: 'Review the order details above before approving. Once approved, the purchase order will be sent to the vendor for fulfillment.'
      },
      width: 'full',
      order: 2
    });

    // 🔥 FIX: Approval buttons rendered via TextBlock (special variant)
    components.push({
      id: 'om-actions',
      component: 'TextBlock',
      props: {
        title: 'Actions',
        content: '__ORDER_APPROVAL_ACTIONS__', // Signal for ArtifactRenderer to show buttons
        variant: 'default'
      },
      width: 'full',
      order: 3
    });

    return { components };
  }

  // ─────────────────────────────────────────────
  // NOTIFIER - 🔥 FIX: quotes + timestamp + overflow
  // ─────────────────────────────────────────────
  private static generateNotifierLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];

    // 🔥 FIX: Remove surrounding quotes from strings
    const stripQuotes = (s: any): string => {
      if (typeof s !== 'string') return String(s ?? '');
      return s.replace(/^["']|["']$/g, '').trim();
    };

    // 🔥 FIX: Format ISO timestamp to human-readable
    const formatTs = (ts: any): string => {
      if (!ts) return 'N/A';
      const d = new Date(String(ts));
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: true
      });
    };

    const metrics: Record<string, string> = {
      'Channel':           stripQuotes(data?.channel ?? 'N/A'),
      'Notification Type': stripQuotes(data?.notification_type ?? data?.type ?? 'info'),
      'Sent At':           formatTs(data?.sent_at ?? data?.timestamp ?? data?.created_at)
    };

    components.push({
      id: 'notif-meta',
      component: 'MetricsGrid',
      props: { metrics, variant: 'default' },
      width: 'full',
      order: 1
    });

    // Message as TextBlock (not MetricsGrid - avoids overflow)
    const message = stripQuotes(data?.message ?? data?.content ?? '');
    if (message.length > 0) {
      components.push({
        id: 'notif-msg',
        component: 'TextBlock',
        props: { title: 'Message', content: message, variant: 'info' },
        width: 'full',
        order: 2
      });
    }

    // Status
    components.push({
      id: 'notif-status',
      component: 'Alert',
      props: {
        type: 'success',
        title: 'Notification Sent',
        message: `Alert successfully dispatched via ${stripQuotes(data?.channel ?? 'channel')}.`
      },
      width: 'full',
      order: 3
    });

    return { components };
  }

  // ─────────────────────────────────────────────
  // VISUALIZER - 🔥 FIX: actual chart + no [object Object]
  // ─────────────────────────────────────────────
  private static generateVisualizerLayout(data: any): GeneratedLayout {
    const components: LayoutComponent[] = [];
    const chartSpec = data?.chart_spec ?? {};
    const rawChartData = data?.chart_data ?? data?.data ?? [];

    // 🔥 FIX: Render the actual chart
    if (Array.isArray(rawChartData) && rawChartData.length > 0) {
      const xKey = chartSpec?.x_axis ?? chartSpec?.x ?? 'date';
      const yKey = chartSpec?.y_axis ?? chartSpec?.y ?? 'sales';
      const chartType = (chartSpec?.chart_type ?? chartSpec?.type ?? 'bar').toLowerCase();
      const validType = ['line', 'bar', 'area'].includes(chartType) ? chartType : 'bar';

      components.push({
        id: 'viz-chart',
        component: 'ChartCard',
        props: {
          data: rawChartData,
          xKey,
          yKey,
          title: chartSpec?.title ?? 'Data Visualization',
          type: validType,
          color: '#4A90E2'
        },
        width: 'full',
        order: 1
      });
    }

    // 🔥 FIX: Spec summary - only show string/number values, skip nested objects
    const specMetrics: Record<string, string> = {};
    for (const [key, val] of Object.entries(chartSpec)) {
      if (key === 'additional_params') continue; // skip nested
      if (val === null || val === undefined) continue;
      if (typeof val === 'object') continue; // skip objects
      specMetrics[this.formatLabel(key)] = String(val);
    }

    if (Object.keys(specMetrics).length > 0) {
      components.push({
        id: 'viz-spec',
        component: 'MetricsGrid',
        props: { metrics: specMetrics, title: 'Chart Configuration' },
        width: 'full',
        order: 2
      });
    }

    // additional_params as JSON if it's meaningful
    const additionalParams = chartSpec?.additional_params;
    if (additionalParams && typeof additionalParams === 'object' && Object.keys(additionalParams).length > 0) {
      components.push({
        id: 'viz-params',
        component: 'JsonViewer',
        props: { data: additionalParams, title: 'Additional Parameters' },
        width: 'full',
        order: 3
      });
    }

    // Fallback when no chart data
    if (components.length === 0) {
      components.push(this.createJsonViewer(data, 'Visualization Data'));
    }

    return { components };
  }

  // ─────────────────────────────────────────────
  // GENERIC HELPERS
  // ─────────────────────────────────────────────
  private static createMetricsGrid(data: any, schema: InferredSchema): LayoutComponent {
    const metrics: Record<string, string> = {};
    for (const field of schema.fields) {
      const value = data[field.key];
      if (value !== null && value !== undefined && typeof value !== 'object') {
        metrics[field.label ?? field.key] = this.formatValue(value, field.format);
      }
    }
    return { id: 'metrics-grid', component: 'MetricsGrid', props: { metrics }, width: 'full', order: 1 };
  }

  private static createDataTable(data: any[], schema: InferredSchema): LayoutComponent {
    return {
      id: 'data-table',
      component: 'DataTable',
      props: {
        data,
        columns: schema.fields.map(f => ({ key: f.key, label: f.label ?? f.key, format: f.format }))
      },
      width: 'full',
      order: 2
    };
  }

  private static createChart(data: any[], schema: InferredSchema): LayoutComponent {
    const dateField = schema.fields.find(f => f.type === 'date' || f.format === 'date' || f.format === 'datetime');
    const numericFields = schema.fields.filter(f => f.type === 'number');
    return {
      id: 'time-series-chart',
      component: 'ChartCard',
      props: {
        data,
        xKey: dateField?.key ?? schema.fields[0]?.key,
        yKey: numericFields[0]?.key ?? schema.fields[1]?.key,
        title: 'Time Series Data',
        type: 'line'
      },
      width: 'full',
      order: 1
    };
  }

  private static createJsonViewer(data: any, title?: string): LayoutComponent {
    return { id: 'json-viewer', component: 'JsonViewer', props: { data, title }, width: 'full', order: 99 };
  }

  private static generateNestedLayout(data: any, schema: InferredSchema): LayoutComponent[] {
    const components: LayoutComponent[] = [];

    for (const field of schema.fields) {
      const value = data[field.key];
      if (field.type === 'object' && value !== null && SchemaInferenceEngine.isKeyValue(value)) {
        const flatMetrics: Record<string, string> = {};
        for (const [k, v] of Object.entries(value)) {
          if (typeof v !== 'object') flatMetrics[this.formatLabel(k)] = String(v);
        }
        if (Object.keys(flatMetrics).length > 0) {
          components.push({
            id: `nested-${field.key}`,
            component: 'MetricsGrid',
            props: { metrics: flatMetrics, title: field.label },
            width: 'half',
            order: components.length + 1
          });
        }
      } else if (field.type === 'array' && Array.isArray(value) && SchemaInferenceEngine.isTabular(value)) {
        const arraySchema = SchemaInferenceEngine.infer(value);
        components.push(this.createDataTable(value, arraySchema));
      }
    }

    if (components.length === 0) {
      components.push(this.createMetricsGrid(data, schema));
    }

    return components;
  }

  private static formatValue(value: any, format?: string): string {
    if (value === null || value === undefined) return 'N/A';
    switch (format) {
      case 'currency':   return `₹${Number(value).toLocaleString()}`;
      case 'percentage': return `${Number(value).toFixed(1)}%`;
      case 'integer':    return Number(value).toLocaleString();
      case 'decimal':    return Number(value).toFixed(2);
      case 'date':
      case 'datetime':   return new Date(value).toLocaleDateString();
      default:           return String(value);
    }
  }

  private static formatLabel(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, s => s.toUpperCase())
      .trim();
  }
}