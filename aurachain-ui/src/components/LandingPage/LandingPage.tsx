// aurachain-ui/src/components/LandingPage/LandingPage.tsx
import { useEffect, useRef, useLayoutEffect } from "react";
import { Link } from "react-router-dom";
import Lenis from "@studio-freight/lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { 
  LineChart, 
  Database, 
  Layers, 
  BrainCircuit, 
  ArrowRight, 
  Github, 
  InfinityIcon,
  Briefcase,
  TrendingUp,
  BarChart3,
  Bell
} from "lucide-react";

// --- Integrations ---
import { useUIStore } from '../../store/uiStore'; 
import ThemeToggle from '../Shared/ThemeToggle'; 

// Register GSAP
gsap.registerPlugin(ScrollTrigger);

// Utility for cleaner tailwind classes
function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

// --- Data ---
const AGENTS = [
  {
    id: "01",
    title: "Orchestrator",
    model: "Llama 3.3 70B",
    role: "CONTROLLER",
    desc: "Central intelligence unit. Interprets natural language queries, decomposes tasks into agent workflows, and manages execution strategy.",
    icon: <BrainCircuit className="w-5 h-5" />,
  },
  {
    id: "02",
    title: "Data Harvester",
    model: "Llama 4 Scout 17B",
    role: "ETL PIPELINE",
    desc: "Data quality specialist. Sanitizes CSV/Excel/JSON streams, imputes missing values, detects outliers, and validates schemas.",
    icon: <Database className="w-5 h-5" />,
  },
  {
    id: "03",
    title: "Trend Analyst",
    model: "Llama 4 Scout 17B",
    role: "MARKET INTEL",
    desc: "Pattern recognition engine. Analyzes Google Trends, detects seasonality, identifies correlations, and flags market anomalies.",
    icon: <TrendingUp className="w-5 h-5" />,
  },
  {
    id: "04",
    title: "Forecaster",
    model: "Llama 3.3 70B + Prophet",
    role: "TIME SERIES",
    desc: "Demand prediction specialist. Enhanced Facebook Prophet with Indian holidays, regional trends, and custom seasonality patterns.",
    icon: <LineChart className="w-5 h-5" />,
  },
  {
    id: "05",
    title: "MCTS Optimizer",
    model: "Llama 3.3 70B",
    role: "STRATEGY",
    desc: "Inventory optimization engine. Monte Carlo Tree Search explores thousands of scenarios to minimize costs and bullwhip effect.",
    icon: <Layers className="w-5 h-5" />,
  },
  {
    id: "06",
    title: "Visualizer",
    model: "Llama 3.3 70B",
    role: "ANALYTICS",
    desc: "Chart generation engine. Creates Plotly visualizations (line, bar, scatter, heatmap, pie) with automatic insight annotations.",
    icon: <BarChart3 className="w-5 h-5" />,
  },
  {
    id: "07",
    title: "Order Manager",
    model: "Llama 3.1 8B",
    role: "PROCUREMENT",
    desc: "Purchase order automation. Drafts vendor orders with approval workflow (human-in-the-loop) and tracks order lifecycle.",
    icon: <Briefcase className="w-5 h-5" />,
  },
  {
    id: "08",
    title: "Notifier",
    model: "Llama 3.1 8B",
    role: "ALERTS",
    desc: "Communication hub. Sends critical alerts via Discord webhooks for stockouts, order confirmations, and anomaly detection.",
    icon: <Bell className="w-5 h-5" />,
  }
];

const METRICS = [
  { label: "Active Agents", value: "08" },
  { label: "LLM Providers", value: "03" },
  { label: "Avg Latency", value: "98ms" },
];

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const { isDarkMode } = useUIStore();

  // Sync Dark Mode manually for GSAP/Lenis context
  useEffect(() => {
    const root = window.document.documentElement;
    if (isDarkMode) root.classList.add('dark');
    else root.classList.remove('dark');
  }, [isDarkMode]);

  // Lenis Scroll
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      touchMultiplier: 2,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    return () => lenis.destroy();
  }, []);

  // GSAP Animations
  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      // 1. Marquee Animation
      if (marqueeRef.current) {
        gsap.to(marqueeRef.current, {
          xPercent: -50,
          ease: "none",
          duration: 30,
          repeat: -1,
        });
      }

      // 2. Reveal Grid Lines
      gsap.utils.toArray<HTMLElement>(".border-reveal").forEach((el) => {
        gsap.from(el, {
          scrollTrigger: {
            trigger: el,
            start: "top 95%",
          },
          scaleX: 0,
          transformOrigin: "left center",
          duration: 1.5,
          ease: "expo.out"
        });
      });

      // 3. Hero Text Stagger
      gsap.from(".hero-char", {
        y: 100,
        opacity: 0,
        stagger: 0.05,
        duration: 0.8,
        ease: "power3.out",
        delay: 0.2
      });

    }, containerRef);
    return () => ctx.revert();
  }, []);

  // Filter out the Orchestrator for the "Spokes" view
  const workerAgents = AGENTS.filter(agent => agent.id !== "01");

  return (
    <div 
      ref={containerRef} 
      className={cn(
        "bg-light-bg dark:bg-black min-h-screen text-slate-900 dark:text-zinc-100",
        "font-sans selection:bg-primary selection:text-white transition-colors duration-500"
      )}
    >
      
      {/* Grid Background Pattern */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-[0.03] dark:opacity-[0.15]" 
           style={{ 
             backgroundImage: `linear-gradient(currentColor 1px, transparent 1px), linear-gradient(90deg, currentColor 1px, transparent 1px)`, 
             backgroundSize: '40px 40px' 
           }} 
      />

      {/* --- Header --- */}
      <header className="fixed top-0 w-full z-50 border-b border-light-border dark:border-zinc-800 bg-light-bg/90 dark:bg-black/90 backdrop-blur-sm transition-colors duration-300">
        <div className="flex justify-between items-center h-16 px-6">
          
          {/* Logo Section */}
          <div className="flex items-center gap-3 group cursor-pointer">
            <InfinityIcon 
              size={30} 
              className="text-primary transition-transform duration-700 ease-in-out group-hover:rotate-180" 
              strokeWidth={2.5} 
            /> 
            <span className="font-heading font-bold tracking-tight text-lg text-slate-900 dark:text-white">
              AURACHAIN
              <span className="text-accent-slate dark:text-zinc-500 font-normal ml-1 text-sm font-mono">v1.0</span>
            </span>
          </div>
          
          <div className="flex items-center gap-6">
            <nav className="hidden md:flex items-center gap-6 mr-2 border-r border-light-border dark:border-zinc-800 pr-6 h-6">
              <Link 
                to="/about" 
                className="text-[13px] font-mono font-bold text-slate-600 dark:text-zinc-400 hover:text-primary dark:hover:text-primary transition-colors uppercase tracking-widest flex items-center gap-2 group"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-transparent group-hover:bg-primary border border-slate-400 dark:border-zinc-600 transition-colors"></span>
                About
              </Link>
            </nav>

            <a 
              href="https://github.com/Moin333/TEAM-LEVI-MUMBAIHACKS" 
              target="_blank" 
              rel="noreferrer" 
              className="hidden md:flex items-center gap-2 text-xs font-mono text-accent-slate dark:text-zinc-400 hover:text-primary dark:hover:text-primary transition-colors"
            >
              <Github className="w-4 h-4" />
              <span className="uppercase tracking-wide">Source</span>
            </a>
            
            <ThemeToggle />
            
            <Link 
              to="/app" 
              className="px-5 py-2 bg-primary text-white text-xs font-bold font-mono uppercase tracking-wider hover:bg-primary-600 transition-colors shadow-lg shadow-primary/20"
            >
              Console
            </Link>
          </div>
        </div>
      </header>

      {/* --- Hero --- */}
      <section className="relative pt-32 pb-20 px-6 border-b border-light-border dark:border-zinc-800">
        <div className="max-w-screen-2xl mx-auto">
          <div className="mb-8 flex items-center gap-2 text-xs font-mono text-primary">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            SYSTEM_STATUS: ONLINE
          </div>

          <h1 className="font-heading text-6xl md:text-8xl lg:text-[8rem] font-bold leading-[0.9] tracking-tight mb-12 text-slate-900 dark:text-white">
            <div className="overflow-hidden"><span className="hero-char block">MULTI-AGENT</span></div>
            <div className="overflow-hidden"><span className="hero-char block text-primary-300 dark:text-primary-600/80">INTELLIGENCE</span></div>
            <div className="overflow-hidden"><span className="hero-char block">PLATFORM</span></div>
          </h1>

          <div className="flex flex-col md:flex-row items-end justify-between gap-12 max-w-6xl">
            <p className="text-lg md:text-xl max-w-xl leading-relaxed text-accent-slate dark:text-zinc-400 font-sans">
              A production-grade orchestration layer for MSME analytics. 
              Deploys 8 specialized autonomous agents using the <span className="text-slate-900 dark:text-white font-semibold underline decoration-light-border dark:decoration-zinc-700 underline-offset-4">Model Context Protocol</span> to forecast revenue, optimize inventory, and automate procurement.
            </p>
            
            <div className="flex gap-4 w-full md:w-auto">
              <Link 
                to="/app" 
                className="group relative flex-1 md:flex-none flex items-center justify-center gap-3 px-10 py-5 overflow-hidden font-mono text-lg font-bold uppercase tracking-widest transition-all duration-300 border-2 border-slate-900 dark:border-zinc-100 text-slate-900 dark:text-white hover:border-primary dark:hover:border-primary focus:outline-none focus:ring-4 focus:ring-primary/20"
              >
                <span className="absolute inset-0 w-full h-full bg-primary -translate-x-full group-hover:translate-x-0 transition-transform duration-500 ease-[cubic-bezier(0.19,1,0.22,1)]"></span>
                <span className="relative z-10 flex items-center gap-3 transition-colors duration-500 group-hover:text-white">
                  INITIALIZE_SYSTEM 
                  <ArrowRight className="w-5 h-5 transition-transform duration-500 group-hover:translate-x-1" />
                </span>
                <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-current opacity-100 group-hover:text-white transition-colors duration-500" />
                <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-current opacity-100 group-hover:text-white transition-colors duration-500" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* --- Marquee --- */}
      <div className="relative z-20 border-b border-light-border dark:border-zinc-800 overflow-hidden bg-light-surface dark:bg-zinc-900 py-3">
        <div ref={marqueeRef} className="flex whitespace-nowrap text-3xl md:text-5xl font-heading font-bold text-zinc-300 dark:text-zinc-700 uppercase tracking-tight select-none">
          <span>Production Ready /// 8 Autonomous Agents /// FastAPI + Redis /// Multi-Model /// </span>
          <span>Production Ready /// 8 Autonomous Agents /// FastAPI + Redis /// Multi-Model /// </span>
          <span>Production Ready /// 8 Autonomous Agents /// FastAPI + Redis /// Multi-Model /// </span>
        </div>
      </div>

      {/* --- Agents Grid (ALL 8 AGENTS) --- */}
      <section className="bg-light-bg dark:bg-black">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
          <div className="col-span-1 md:col-span-2 lg:col-span-4 p-8 border-b border-light-border dark:border-zinc-800">
            <h2 className="text-xs font-mono text-primary mb-2">01 // AGENT_ECOSYSTEM</h2>
            <h3 className="text-3xl font-heading font-bold text-slate-900 dark:text-white">8 Autonomous Worker Nodes</h3>
          </div>

          {AGENTS.map((agent, i) => (
            <div 
              key={i} 
              className={cn(
                "group relative border-b border-r border-light-border dark:border-zinc-800",
                "p-8 h-[400px] flex flex-col justify-between bg-light-bg dark:bg-black",
                "transition-colors hover:bg-light-surface dark:hover:bg-zinc-900"
              )}
            >
              <div className="border-reveal absolute top-0 left-0 w-full h-[2px] bg-primary z-10" />
              <div>
                <div className="flex justify-between items-start mb-6">
                  <div className="w-10 h-10 flex items-center justify-center border border-light-border dark:border-zinc-700 bg-light-elevated dark:bg-zinc-900 text-primary">
                    {agent.icon}
                  </div>
                  <span className="font-mono text-xs text-accent-slate dark:text-zinc-500">{agent.id}</span>
                </div>
                <h4 className="text-xl font-heading font-bold mb-2 text-slate-900 dark:text-zinc-100">{agent.title}</h4>
                <div className="inline-block px-2 py-1 bg-light-elevated dark:bg-zinc-900 text-[10px] font-mono uppercase tracking-widest text-accent-slate dark:text-zinc-400 mb-4 border border-light-border dark:border-zinc-700">
                  {agent.model}
                </div>
                <p className="text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
                  {agent.desc}
                </p>
              </div>
              <div className="pt-6 border-t border-dashed border-light-border dark:border-zinc-800 mt-auto flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-accent-teal" />
                <span className="text-[10px] font-mono font-bold text-accent-teal tracking-widest uppercase">
                  ACTIVE
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* --- Technical Specs & Enhanced Architecture --- */}
      <section className="flex flex-col xl:flex-row border-b border-light-border dark:border-zinc-800 min-h-[800px]">
        <div className="xl:w-1/4 p-8 lg:p-12 border-b xl:border-b-0 xl:border-r border-light-border dark:border-zinc-800 bg-light-bg dark:bg-black flex flex-col">
          <h2 className="text-xs font-mono text-primary mb-2">02 // ARCHITECTURE</h2>
          <h3 className="text-4xl font-heading font-bold mb-10 text-slate-900 dark:text-white">Hub & Spoke<br/>Intelligence</h3>
          
          <div className="space-y-0 mb-10">
            {METRICS.map((m, i) => (
               <div key={i} className="flex justify-between items-end border-b border-light-border dark:border-zinc-800 py-4">
                 <span className="text-sm text-accent-slate dark:text-zinc-500 font-mono uppercase tracking-wide">{m.label}</span>
                 <span className="text-2xl font-bold font-mono text-slate-900 dark:text-white">{m.value}</span>
               </div>
            ))}
          </div>
          
          <div className="mt-auto p-4 bg-light-surface dark:bg-zinc-900 border border-light-border dark:border-zinc-800 text-xs text-accent-slate dark:text-zinc-400 font-mono leading-relaxed">
            <span className="text-primary font-bold">NOTE:</span> The Orchestrator uses a dedicated message bus to maintain context across all agent interactions, ensuring zero-hallucination handoffs.
          </div>
        </div>

        {/* --- Enhanced Visual Architecture (SINGLE ROW) --- */}
        <div className="xl:w-3/4 bg-light-surface dark:bg-zinc-950 p-6 lg:p-12 flex flex-col justify-center overflow-hidden relative">
          
          <div className="relative w-full border border-light-border dark:border-zinc-700 bg-light-bg dark:bg-black p-8 shadow-2xl flex flex-col items-center rounded-sm">
            <div className="absolute top-2 left-2 text-[10px] font-mono text-accent-slate dark:text-zinc-600">FIG 1.1 ORCHESTRATION FLOW</div>
            
            {/* The Hub (Orchestrator) */}
            <div className="relative z-20 mb-12 w-full flex flex-col items-center">
               <div className="relative group cursor-default">
                 {/* Glowing Effect (CHANGED: Now just Blue/Primary, no purple) */}
                 <div className="absolute -inset-1 bg-primary rounded blur opacity-20 group-hover:opacity-40 transition duration-1000"></div>
                 
                 <div className="relative px-10 py-5 border border-primary bg-light-elevated dark:bg-zinc-900 text-slate-900 dark:text-white font-mono text-sm font-bold tracking-widest rounded shadow-xl flex items-center gap-4 z-10">
                   <div className="p-1.5 bg-primary/10 rounded-full text-primary">
                     <BrainCircuit className="w-6 h-6" />
                   </div>
                   <span>AI ORCHESTRATOR</span>
                   <span className="flex h-2 w-2 relative ml-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                   </span>
                 </div>

                 {/* Central Spine Line */}
                 <div className="absolute left-1/2 top-full w-[2px] h-12 bg-gradient-to-b from-primary to-transparent -translate-x-1/2"></div>
               </div>
            </div>

            {/* The Spoke Layer Container */}
            <div className="relative w-full mt-4">
               {/* 1. The Horizontal Bus Line (Connects all agents) */}
               {/* Adjusted for 7 columns: 100% / 7 = ~14.28%. Center is 7.14% */}
               <div className="hidden lg:block absolute top-0 left-[7.14%] right-[7.14%] h-[1px] border-t border-dashed border-slate-300 dark:border-zinc-600"></div>
               
               {/* 2. Grid Container for Agents (7 Columns) */}
               <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-[repeat(7,minmax(0,1fr))] gap-4 lg:gap-2 pt-8 lg:pt-8 w-full">
                 
                 {/* Map through Worker Agents */}
                 {workerAgents.map((agent, index) => (
                   <div key={index} className="flex flex-col items-center group relative">
                      
                      {/* Connection Line to Bus (Desktop) */}
                      <div className="hidden lg:block absolute -top-8 left-1/2 w-[1px] h-8 border-l border-dashed border-slate-300 dark:border-zinc-700 group-hover:border-primary group-hover:border-solid transition-colors duration-300 origin-top"></div>
                      
                      {/* Agent Card */}
                      <div className="w-full aspect-[4/5] lg:aspect-auto lg:h-32 border border-light-border dark:border-zinc-800 bg-light-elevated dark:bg-zinc-900 hover:bg-light-surface dark:hover:bg-zinc-800 p-3 flex flex-col items-center justify-center gap-3 transition-all duration-300 hover:border-primary hover:-translate-y-1 hover:shadow-lg rounded-sm cursor-default">
                         <div className="text-slate-400 dark:text-zinc-500 group-hover:text-primary transition-colors duration-300 transform group-hover:scale-110">
                           {agent.icon}
                         </div>
                         <div className="text-center">
                           <span className="block text-[9px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1 leading-tight">{agent.title}</span>
                           <span className="block text-[8px] text-accent-slate dark:text-zinc-600 font-mono">{agent.id}</span>
                         </div>
                      </div>
                   </div>
                 ))}

               </div>
            </div>

            {/* Bottom Status Bar */}
            <div className="mt-12 flex items-center justify-between w-full px-4 py-2 border-t border-light-border dark:border-zinc-800 bg-light-surface/50 dark:bg-zinc-900/30">
               <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-1 h-1 bg-primary rounded-full animate-pulse"></div>
                    <div className="w-1 h-1 bg-primary rounded-full animate-pulse delay-75"></div>
                    <div className="w-1 h-1 bg-primary rounded-full animate-pulse delay-150"></div>
                  </div>
                  <span className="text-[9px] font-mono text-primary uppercase tracking-widest">Data Stream Active</span>
               </div>
               <div className="text-[9px] font-mono text-slate-400 dark:text-zinc-600">
                  LATENCY: 42ms
               </div>
            </div>

          </div>
        </div>
      </section>

      {/* --- Footer --- */}
      <footer className="bg-light-bg dark:bg-black py-12 px-6 border-t border-light-border dark:border-zinc-800">
        <div className="max-w-screen-2xl mx-auto flex flex-col md:flex-row justify-between items-end gap-8">
           <div>
             <div className="flex items-center gap-2 mb-4 group cursor-pointer">
               <InfinityIcon 
                 size={30} 
                 className="text-primary transition-transform duration-700 ease-in-out group-hover:rotate-180" 
                 strokeWidth={2.5} 
               /> 
               <span className="font-heading font-bold tracking-tight text-slate-900 dark:text-white">AURACHAIN</span>
             </div>
             <p className="text-sm text-accent-slate dark:text-zinc-500 max-w-xs font-sans">
               AI-Native Multi-Agent System for Micro, Small, and Medium Enterprises.
             </p>
           </div>
           
           <div className="text-right">
              <Link 
                to="/app" 
                className="group relative inline-flex items-center justify-center px-8 py-3 overflow-hidden font-mono font-bold tracking-tighter text-slate-900 dark:text-white border border-slate-900 dark:border-zinc-100 rounded-sm transition-all duration-300 hover:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
              >
                <span className="absolute inset-0 w-full h-full bg-primary -translate-x-full group-hover:translate-x-0 transition-transform duration-500 ease-[cubic-bezier(0.19,1,0.22,1)]"></span>
                <span className="relative z-10 flex items-center gap-3 transition-colors duration-500 group-hover:text-white">
                  ENTER DASHBOARD 
                  <ArrowRight className="w-4 h-4 transition-transform duration-500 group-hover:translate-x-1" />
                </span>
              </Link>
              
              <div className="text-[10px] font-mono text-accent-slate dark:text-zinc-600 mt-2">
                © {new Date().getFullYear()} AURACHAIN // SYSTEM_READY
              </div>
           </div>
        </div>
      </footer>

    </div>
  );
}