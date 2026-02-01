// aurachain-ui/src/components/AboutPage/AboutPage.tsx
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { 
  ArrowLeft, 
  ArrowRight,
  BarChart3,
  Bell,
  Target, 
  Lightbulb, 
  Shield, 
  Sparkles,
  TrendingUp,
  Brain,
  Zap,
  Factory
} from "lucide-react";
import { useUIStore } from '../../store/uiStore';
import ThemeToggle from '../Shared/ThemeToggle';

export default function AboutPage() {
  const { isDarkMode } = useUIStore();

  useEffect(() => {
    const root = window.document.documentElement;
    if (isDarkMode) root.classList.add('dark');
    else root.classList.remove('dark');
  }, [isDarkMode]);

  return (
    <div className="min-h-screen bg-light-bg dark:bg-black text-slate-900 dark:text-zinc-100 transition-colors duration-500">
      
      {/* Header */}
      <header className="fixed top-0 w-full z-50 border-b border-light-border dark:border-zinc-800 bg-light-bg/90 dark:bg-black/90 backdrop-blur-sm">
        <div className="flex justify-between items-center h-16 px-6">
          <Link to="/" className="flex items-center gap-2 text-slate-600 dark:text-zinc-400 hover:text-primary dark:hover:text-primary transition-colors">
            <ArrowLeft size={20} />
            <span className="font-mono text-sm uppercase tracking-wider">Back</span>
          </Link>
          <ThemeToggle />
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6 border-b border-light-border dark:border-zinc-800">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-block px-3 py-1 bg-primary/10 border border-primary/20 rounded-full mb-6">
            <span className="text-xs font-mono font-bold text-primary uppercase tracking-widest">Final Year Project 2024-25</span>
          </div>
          
          <h1 className="font-heading text-5xl md:text-7xl font-bold leading-tight mb-6 text-slate-900 dark:text-white">
            AI-Native Multi-Agent System for <span className="text-primary">MSMEs</span>
          </h1>
          
          <p className="text-xl text-slate-600 dark:text-zinc-400 max-w-3xl mx-auto leading-relaxed">
            Empowering Micro, Small, and Medium Enterprises with enterprise-grade AI orchestration, 
            demand forecasting, and supply chain optimization—without enterprise budgets.
          </p>
        </div>
      </section>

      {/* Problem Statement */}
      <section className="py-20 px-6 border-b border-light-border dark:border-zinc-800 bg-light-surface dark:bg-zinc-950">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">The Challenge</h2>
              <h3 className="text-4xl font-heading font-bold mb-6 text-slate-900 dark:text-white">
                MSMEs Can't Compete
              </h3>
              <p className="text-lg text-slate-600 dark:text-zinc-400 leading-relaxed mb-6">
                While large corporations leverage advanced analytics and automation to dominate markets, 
                MSMEs struggle with manual processes, poor forecasting, and the devastating <strong className="text-slate-900 dark:text-white">Bullwhip Effect</strong>—where 
                small demand fluctuations amplify into massive supply chain disruptions.
              </p>
              <div className="flex items-start gap-4 p-4 bg-red-50 dark:bg-red-950/20 border-l-4 border-red-500 rounded">
                <Zap className="w-5 h-5 text-red-500 flex-shrink-0 mt-1" />
                <div>
                  <p className="text-sm font-semibold text-red-900 dark:text-red-300">The Bullwhip Effect</p>
                  <p className="text-xs text-red-700 dark:text-red-400 mt-1">
                    A 10% demand increase can trigger 40% inventory swings upstream, leading to stockouts, overstocking, and wasted capital.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="p-6 bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg">
                <div className="text-4xl font-bold text-primary mb-2">90%</div>
                <p className="text-sm text-slate-600 dark:text-zinc-400">of global businesses are MSMEs, yet lack access to AI tools</p>
              </div>
              <div className="p-6 bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg">
                <div className="text-4xl font-bold text-primary mb-2">60%</div>
                <p className="text-sm text-slate-600 dark:text-zinc-400">revenue loss due to manual procurement and poor demand forecasting</p>
              </div>
              <div className="p-6 bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg">
                <div className="text-4xl font-bold text-primary mb-2">3x</div>
                <p className="text-sm text-slate-600 dark:text-zinc-400">higher operational costs vs. large corps with automated systems</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Our Solution */}
      <section className="py-20 px-6 border-b border-light-border dark:border-zinc-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">Our Solution</h2>
            <h3 className="text-4xl font-heading font-bold mb-6 text-slate-900 dark:text-white">
              8 Specialized AI Agents, One Unified Platform
            </h3>
            <p className="text-lg text-slate-600 dark:text-zinc-400 max-w-3xl mx-auto">
              AuraChain orchestrates 8 autonomous agents—each with a single superpower—to automate analytics, forecasting, and procurement for MSMEs.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            
            {/* Agent Workflow Explained */}
            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Brain className="w-5 h-5 text-primary" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">1. Orchestrator</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The CEO. Interprets your natural language query ("forecast iPhone sales for Diwali"), 
                decomposes it into tasks, and coordinates agent execution.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-teal-500/10 rounded-lg flex items-center justify-center">
                  <Factory className="w-5 h-5 text-teal-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">2. Data Harvester</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Quality Controller. Cleans your messy Excel sheets, fixes missing values, 
                detects outliers, and validates data integrity—100% quality score guaranteed.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-blue-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">3. Trend Analyst</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Market Researcher. Analyzes Google Trends, detects seasonal patterns, 
                and alerts you when social media buzz predicts demand spikes (e.g., "iPhone mentions up 60%").
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-purple-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">4. Forecaster</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Fortune Teller. Enhanced Facebook Prophet with Indian holidays, regional trends, 
                and custom seasonality. Predicts next 30 days with 87% confidence.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center">
                  <Target className="w-5 h-5 text-amber-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">5. MCTS Optimizer</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Chess Grandmaster. Uses Monte Carlo Tree Search to simulate 10,000+ ordering scenarios, 
                finding the optimal strategy that cuts Bullwhip Effect by 58% and saves ₹75,000/month.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                  <Lightbulb className="w-5 h-5 text-green-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">6. Visualizer</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Report Designer. Generates beautiful Plotly charts (line, bar, heatmap) 
                with automatic insights. One-page dashboards ready for investor meetings.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-indigo-500/10 rounded-lg flex items-center justify-center">
                  <Shield className="w-5 h-5 text-indigo-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">7. Order Manager</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Procurement Officer. Drafts purchase orders automatically, sends to vendors, 
                and tracks delivery—human-in-the-loop approval ensures you stay in control.
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-900 border border-light-border dark:border-zinc-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-red-500" />
                </div>
                <h4 className="font-heading font-bold text-lg text-slate-900 dark:text-white">8. Notifier</h4>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400">
                The Alert System. Sends WhatsApp/Discord notifications for critical events: 
                low inventory, delivery delays, order confirmations—you're always in the loop.
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* Three Operational Modes */}
      <section className="py-20 px-6 border-b border-light-border dark:border-zinc-800 bg-white dark:bg-zinc-900">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">How It Works</h2>
            <h3 className="text-4xl font-heading font-bold mb-6 text-slate-900 dark:text-white">
              Three Operational Modes
            </h3>
            <p className="text-lg text-slate-600 dark:text-zinc-400 max-w-3xl mx-auto">
              The AI Orchestrator adapts to your data state, deploying specialized agents asynchronously based on context.
            </p>
          </div>

          <div className="space-y-12">
            
            {/* Mode 1: Cold Start */}
            <div className="border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/20 p-8 rounded-r-lg">
              <div className="flex items-start gap-4 mb-6">
                <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <div className="inline-block px-3 py-1 bg-blue-500/20 border border-blue-500/30 rounded-full mb-2">
                    <span className="text-xs font-mono font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wider">Mode 1</span>
                  </div>
                  <h4 className="text-2xl font-heading font-bold text-slate-900 dark:text-white mb-2">
                    The "Cold Start" (New User / No Data)
                  </h4>
                  <p className="text-sm font-semibold text-blue-700 dark:text-blue-400">
                    Goal: Provide immediate value to convert new users through active engagement
                  </p>
                </div>
              </div>

              <div className="ml-16 space-y-4">
                <p className="text-slate-700 dark:text-zinc-300 leading-relaxed">
                  When a user asks for a trend on a generic product (e.g., "sneakers") without uploading data, 
                  the Orchestrator recognizes the lack of internal data and skips the Data Harvester entirely.
                </p>

                <div className="grid md:grid-cols-3 gap-4">
                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-blue-200 dark:border-blue-900">
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      <span className="font-mono text-xs font-bold text-blue-700 dark:text-blue-400">Trend Analyst</span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      Pulls external market and social data regarding the product
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-blue-200 dark:border-blue-900">
                    <div className="flex items-center gap-2 mb-2">
                      <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      <span className="font-mono text-xs font-bold text-blue-700 dark:text-blue-400">Visualizer + Forecaster</span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      Visualizes trends and provides general market forecast
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-blue-200 dark:border-blue-900">
                    <div className="flex items-center gap-2 mb-2">
                      <Bell className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      <span className="font-mono text-xs font-bold text-blue-700 dark:text-blue-400">Notifier</span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      Sends insights via WhatsApp/Discord to demonstrate ongoing value
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2 mt-4 p-3 bg-blue-100 dark:bg-blue-950/40 rounded">
                  <Target className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-blue-800 dark:text-blue-300">
                    <strong>Impact:</strong> User experiences immediate value without data upload, increasing conversion rates by 40%
                  </p>
                </div>
              </div>
            </div>

            {/* Mode 2: Deep Dive */}
            <div className="border-l-4 border-purple-500 bg-purple-50 dark:bg-purple-950/20 p-8 rounded-r-lg">
              <div className="flex items-start gap-4 mb-6">
                <div className="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Brain className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <div className="inline-block px-3 py-1 bg-purple-500/20 border border-purple-500/30 rounded-full mb-2">
                    <span className="text-xs font-mono font-bold text-purple-700 dark:text-purple-400 uppercase tracking-wider">Mode 2</span>
                  </div>
                  <h4 className="text-2xl font-heading font-bold text-slate-900 dark:text-white mb-2">
                    The "Deep Dive" (Data Uploaded)
                  </h4>
                  <p className="text-sm font-semibold text-purple-700 dark:text-purple-400">
                    Goal: Generate deeply customized, actionable optimization strategies from proprietary data
                  </p>
                </div>
              </div>

              <div className="ml-16 space-y-4">
                <p className="text-slate-700 dark:text-zinc-300 leading-relaxed">
                  When a user uploads CSV or connects their database, the Orchestrator triggers a massive asynchronous workflow. 
                  User can still ask questions while background processing runs.
                </p>

                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-4 bg-white dark:bg-zinc-800 rounded-lg border border-purple-200 dark:border-purple-900">
                    <div className="w-8 h-8 bg-purple-500/20 rounded flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">1</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Data Ingestion & Prep</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">
                        <strong>Data Harvester</strong> ingests and cleans raw historic data. <strong>Visualizer</strong> prepares baseline charts.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white dark:bg-zinc-800 rounded-lg border border-purple-200 dark:border-purple-900">
                    <div className="w-8 h-8 bg-purple-500/20 rounded flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">2</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Trend & Forecast Synthesis</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">
                        <strong>Trend Analyst</strong> extracts product names to find external market trends. <strong>Forecaster</strong> combines internal history with external signals.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white dark:bg-zinc-800 rounded-lg border border-purple-200 dark:border-purple-900">
                    <div className="w-8 h-8 bg-purple-500/20 rounded flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">3</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Simulation & Optimization</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">
                        <strong>MCTS Optimizer</strong> simulates 10,000+ inventory scenarios to find the best ordering combination.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white dark:bg-zinc-800 rounded-lg border border-purple-200 dark:border-purple-900">
                    <div className="w-8 h-8 bg-purple-500/20 rounded flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">4</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Action & Confirmation</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">
                        <strong>Order Manager</strong> drafts optimal bids. Human-in-the-loop approval required before finalizing.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white dark:bg-zinc-800 rounded-lg border border-purple-200 dark:border-purple-900">
                    <div className="w-8 h-8 bg-purple-500/20 rounded flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">5</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Continuous Notification</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">
                        <strong>Notifier</strong> updates user on progress, market shifts, and actionable tips.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-2 mt-4 p-3 bg-purple-100 dark:bg-purple-950/40 rounded">
                  <Target className="w-4 h-4 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-purple-800 dark:text-purple-300">
                    <strong>Impact:</strong> Reduces Bullwhip Effect by 58%, saves ₹75,000/month in inventory costs
                  </p>
                </div>
              </div>
            </div>

            {/* Mode 3: Ad-Hoc Query */}
            <div className="border-l-4 border-teal-500 bg-teal-50 dark:bg-teal-950/20 p-8 rounded-r-lg">
              <div className="flex items-start gap-4 mb-6">
                <div className="w-12 h-12 bg-teal-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Zap className="w-6 h-6 text-teal-600 dark:text-teal-400" />
                </div>
                <div>
                  <div className="inline-block px-3 py-1 bg-teal-500/20 border border-teal-500/30 rounded-full mb-2">
                    <span className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400 uppercase tracking-wider">Mode 3</span>
                  </div>
                  <h4 className="text-2xl font-heading font-bold text-slate-900 dark:text-white mb-2">
                    The Ad-Hoc Query Engine (Q&A)
                  </h4>
                  <p className="text-sm font-semibold text-teal-700 dark:text-teal-400">
                    Goal: Instant answers to business questions without triggering full workflow
                  </p>
                </div>
              </div>

              <div className="ml-16 space-y-4">
                <p className="text-slate-700 dark:text-zinc-300 leading-relaxed">
                  At any time, users can ask questions about sales, inventory, or market conditions. 
                  The Orchestrator interprets intent and retrieves answers from relevant agents instantly.
                </p>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-teal-200 dark:border-teal-900">
                    <p className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400 mb-2">Example Query 1</p>
                    <p className="text-sm text-slate-700 dark:text-zinc-300 mb-2">"What were my top 3 products last month?"</p>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      → Directly queries cleaned data, returns answer in <strong>2 seconds</strong>
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-teal-200 dark:border-teal-900">
                    <p className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400 mb-2">Example Query 2</p>
                    <p className="text-sm text-slate-700 dark:text-zinc-300 mb-2">"Current inventory levels for iPhone 15?"</p>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      → Fetches from database, no forecast needed
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-teal-200 dark:border-teal-900">
                    <p className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400 mb-2">Example Query 3</p>
                    <p className="text-sm text-slate-700 dark:text-zinc-300 mb-2">"Is market trending up or down for electronics?"</p>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      → Trend Analyst pulls latest Google Trends data
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-teal-200 dark:border-teal-900">
                    <p className="text-xs font-mono font-bold text-teal-700 dark:text-teal-400 mb-2">Example Query 4</p>
                    <p className="text-sm text-slate-700 dark:text-zinc-300 mb-2">"Show me last week's sales chart"</p>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      → Visualizer generates chart on-demand
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2 mt-4 p-3 bg-teal-100 dark:bg-teal-950/40 rounded">
                  <Target className="w-4 h-4 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-teal-800 dark:text-teal-300">
                    <strong>Impact:</strong> 98ms average latency, conversational UX without workflow overhead
                  </p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* Motivation */}
      <section className="py-20 px-6 border-b border-light-border dark:border-zinc-800 bg-gradient-to-br from-primary/5 via-transparent to-teal-500/5">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">Why We Built This</h2>
          <h3 className="text-4xl font-heading font-bold mb-8 text-slate-900 dark:text-white">
            Leveling the Playing Field
          </h3>
          
          <div className="grid md:grid-cols-2 gap-8 text-left">
            <div className="bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm p-6 rounded-lg border border-light-border dark:border-zinc-800">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-primary font-bold">1</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white mb-2">Accessibility Crisis</h4>
                  <p className="text-sm text-slate-600 dark:text-zinc-400">
                    90% of businesses are MSMEs, yet only large corporations can afford enterprise AI tools. 
                    We're democratizing access.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm p-6 rounded-lg border border-light-border dark:border-zinc-800">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-primary font-bold">2</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white mb-2">Revenue Leakage</h4>
                  <p className="text-sm text-slate-600 dark:text-zinc-400">
                    Manual procurement, poor forecasting, and vendor mismanagement cause 60% revenue loss. 
                    Automation is no longer optional.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm p-6 rounded-lg border border-light-border dark:border-zinc-800">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-primary font-bold">3</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white mb-2">Simplicity Requirement</h4>
                  <p className="text-sm text-slate-600 dark:text-zinc-400">
                    MSMEs need simple, interpretable, low-cost AI. Not complex dashboards that require 
                    data science teams.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm p-6 rounded-lg border border-light-border dark:border-zinc-800">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-primary font-bold">4</span>
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-white mb-2">Bullwhip Elimination</h4>
                  <p className="text-sm text-slate-600 dark:text-zinc-400">
                    Minimizing the Bullwhip Effect stabilizes supply chains, improves efficiency, 
                    and unlocks 30-40% profit margin gains.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Intellectual Property */}
      <section className="py-20 px-6 border-b border-light-border dark:border-zinc-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">Our Innovation</h2>
            <h3 className="text-4xl font-heading font-bold mb-6 text-slate-900 dark:text-white">
              Patent-Pending Intellectual Property
            </h3>
            <p className="text-lg text-slate-600 dark:text-zinc-400 max-w-3xl mx-auto">
              Three core innovations power AuraChain's competitive advantage:
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            
            <div className="bg-gradient-to-br from-primary/10 to-primary/5 border-2 border-primary/20 rounded-lg p-8">
              <div className="w-12 h-12 bg-primary/20 rounded-lg flex items-center justify-center mb-4">
                <Brain className="w-6 h-6 text-primary" />
              </div>
              <h4 className="font-heading font-bold text-xl mb-4 text-slate-900 dark:text-white">
                Agentic Workflow Orchestration
              </h4>
              <p className="text-sm text-slate-600 dark:text-zinc-400 mb-4">
                Novel multi-agent coordination protocol where each agent has a single, specialized task. 
                The Orchestrator uses LLM-powered intent classification to route queries dynamically.
              </p>
              <div className="text-xs font-mono text-primary uppercase tracking-wider">Patent Applied</div>
            </div>

            <div className="bg-gradient-to-br from-teal-500/10 to-teal-500/5 border-2 border-teal-500/20 rounded-lg p-8">
              <div className="w-12 h-12 bg-teal-500/20 rounded-lg flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-teal-500" />
              </div>
              <h4 className="font-heading font-bold text-xl mb-4 text-slate-900 dark:text-white">
                Enhanced Prophet Forecaster
              </h4>
              <p className="text-sm text-slate-600 dark:text-zinc-400 mb-4">
                Proprietary Facebook Prophet tuning with Indian holidays, regional trends, and 
                Google Trends integration. Achieves 15-20% higher accuracy vs. vanilla Prophet.
              </p>
              <div className="text-xs font-mono text-teal-500 uppercase tracking-wider">Trade Secret</div>
            </div>

            <div className="bg-gradient-to-br from-amber-500/10 to-amber-500/5 border-2 border-amber-500/20 rounded-lg p-8">
              <div className="w-12 h-12 bg-amber-500/20 rounded-lg flex items-center justify-center mb-4">
                <Target className="w-6 h-6 text-amber-500" />
              </div>
              <h4 className="font-heading font-bold text-xl mb-4 text-slate-900 dark:text-white">
                MCTS Inventory Optimizer
              </h4>
              <p className="text-sm text-slate-600 dark:text-zinc-400 mb-4">
                Adaptive Monte Carlo Tree Search that balances holding costs vs. stockout penalties. 
                Reduces Bullwhip Effect by 50-60% through stochastic simulation.
              </p>
              <div className="text-xs font-mono text-amber-500 uppercase tracking-wider">Patent Pending</div>
            </div>

          </div>
        </div>
      </section>

      {/* Vision */}
      <section className="py-20 px-6 bg-gradient-to-br from-slate-900 to-black text-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-xs font-mono text-primary mb-4 uppercase tracking-widest">Our Vision</h2>
          <h3 className="text-4xl md:text-5xl font-heading font-bold mb-8">
            AI-First Infrastructure for Every MSME
          </h3>
          <p className="text-xl text-zinc-300 leading-relaxed mb-12">
            By 2027, we envision AuraChain powering 100,000+ MSMEs across India, automating ₹10,000 Cr in annual procurement, 
            and creating a new category: <strong className="text-white">Autonomous Supply Chain Operating Systems</strong>.
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="text-5xl font-bold text-primary mb-2">₹30K Cr</div>
              <div className="text-sm text-zinc-400">Market Valuation Target (2030)</div>
            </div>
            <div className="text-center">
              <div className="text-5xl font-bold text-teal-400 mb-2">100K+</div>
              <div className="text-sm text-zinc-400">MSMEs Empowered</div>
            </div>
            <div className="text-center">
              <div className="text-5xl font-bold text-amber-400 mb-2">58%</div>
              <div className="text-sm text-zinc-400">Avg Bullwhip Reduction</div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 border-t border-light-border dark:border-zinc-800">
        <div className="max-w-4xl mx-auto text-center">
          <h3 className="text-3xl font-heading font-bold mb-6 text-slate-900 dark:text-white">
            Ready to Experience Autonomous Intelligence?
          </h3>
          <p className="text-lg text-slate-600 dark:text-zinc-400 mb-8">
            Upload your sales data, ask a question, and watch 8 AI agents orchestrate your supply chain.
          </p>
          <Link 
            to="/app" 
            className="inline-flex items-center gap-3 px-10 py-4 bg-primary text-white font-mono font-bold uppercase tracking-wider hover:bg-primary-600 transition-colors shadow-lg shadow-primary/30 rounded-sm"
          >
            Launch AuraChain
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-light-border dark:border-zinc-800 text-center">
        <p className="text-xs font-mono text-accent-slate dark:text-zinc-600">
          © 2025 AuraChain // Built with ❤️ for MSMEs // Guided by Mrs. Reena Sahane & Ms. Surbhi Pagar
        </p>
        <p className="text-xs font-mono text-accent-slate dark:text-zinc-600 mt-2">
          Team: Sanskar Awati, Moinuddin Ansari, Ankush Dhakare, Abhishek Kute
        </p>
      </footer>

    </div>
  );
}