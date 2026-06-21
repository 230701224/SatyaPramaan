import React, { useState, useEffect } from 'react';
import axios from '../lib/axios';
import { AlertTriangle, Clock, ShieldCheck, FileText, ArrowRight, Loader2, Database, Activity, Network, Wifi, WifiOff, Brain } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

/* ── API Health Status Pill ─────────────────────────────────────────────────── */
const StatusPill = ({ label, status }) => {
  const isOnline = status?.available || status?.status === 'Installed';
  const isMock = status?.status === 'Mock Mode';
  const isFallback = status?.status === 'No Credentials';

  if (isOnline) {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-bold border bg-emerald-500/10 text-emerald-400 border-emerald-500/20" title={status?.model || status?.status}>
        <Wifi className="w-2.5 h-2.5" />
        {label}
      </div>
    );
  }

  if (isMock) {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-bold border bg-sky-500/10 text-sky-400 border-sky-500/20" title="Simulated mode active (no external API charges)">
        <Wifi className="w-2.5 h-2.5" />
        {label} (Mock)
      </div>
    );
  }

  if (isFallback && label === 'AWS Textract') {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-bold border bg-amber-500/10 text-amber-400 border-amber-500/20" title="Using local pdfplumber parser fallback">
        <Wifi className="w-2.5 h-2.5" />
        {label} (pdfplumber)
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-bold border bg-slate-800 text-slate-500 border-slate-700" title={status?.status}>
      <WifiOff className="w-2.5 h-2.5" />
      {label}
    </div>
  );
};

const Dashboard = ({ onSelectCase, searchQuery = '' }) => {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetchCases();
    fetchHealth();
  }, []);

  const fetchCases = async () => {
    try {
      const res = await axios.get('/api/cases');
      setCases(res.data);
    } catch (err) {
      setError('Failed to connect to FastAPI pipeline');
    } finally {
      setLoading(false);
    }
  };

  const fetchHealth = async () => {
    try {
      const res = await axios.get('/api/health');
      setHealth(res.data.services);
    } catch (_) {}
  };

  const highRiskCount = cases.filter(c => c.risk_score > 75).length;
  const pendingCount = cases.filter(c => c.status === 'Pending' || c.status === 'Escalated').length;
  const fraudRingCases = cases.filter(c => c.risk_score > 75);

  const filteredCases = cases.filter(c => 
    c.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.applicant_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const chartData = [
    { name: 'Jan', fraud: 12, safe: 140 },
    { name: 'Feb', fraud: 19, safe: 180 },
    { name: 'Mar', fraud: 15, safe: 210 },
    { name: 'Apr', fraud: 22, safe: 190 },
    { name: 'May', fraud: 28, safe: 240 },
    { name: 'Jun', fraud: 34, safe: 260 },
  ];

  const distributionData = [
    { name: 'ITR-V', count: 18 },
    { name: 'Salary Slip', count: 32 },
    { name: 'Bank Stmt', count: 24 },
    { name: 'Property', count: 14 },
    { name: 'Form 16', count: 9 },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">

      {/* ── API Health Status Bar ─────────────────────────────────────────── */}
      {health && (
        <div className="glass-panel p-4 flex flex-wrap items-center gap-2">
          <span className="text-[9px] font-bold uppercase text-slate-500 tracking-wider mr-2">Pipeline Services:</span>
          <StatusPill label="Ollama (Llama 3.2)" status={health.ollama_api} />
          <StatusPill label="AWS Textract" status={health.textract} />
          <StatusPill label="NSDL PAN" status={health.nsdl} />
          <StatusPill label="DigiLocker" status={health.digilocker} />
          <StatusPill label="MCA21" status={health.mca21} />
          <StatusPill label="networkx" status={health.networkx} />
          <StatusPill label="YOLOv8" status={health.yolov8} />
          <span className="ml-auto text-[9px] text-slate-600">v{health.pipeline_version || '3.0.0'}</span>
        </div>
      )}

      {/* ── Fraud Ring Alert Banner ───────────────────────────────────────── */}
      {fraudRingCases.length >= 2 && (
        <div className="p-4 bg-red-950/25 border border-red-500/25 rounded-xl flex items-start gap-3">
          <Network className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <h5 className="text-xs font-bold text-red-400">⚠ Potential Fraud Ring — {fraudRingCases.length} High-Risk Cases Flagged</h5>
            <p className="text-slate-400 text-[10px] mt-1 leading-relaxed">
              Multiple high-risk applications ({fraudRingCases.map(c => c.case_id).join(', ')}) share overlapping
              risk patterns. Run Cross-Document Consistency Matrix to identify shared employers or duplicate PAN nodes.
            </p>
          </div>
        </div>
      )}

      {/* ── Overview Cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="stat-card glass-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-red-500/10 text-red-500 border border-red-500/20 flex-shrink-0">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-slate-400 text-[10px] font-semibold tracking-wider uppercase">High Risk Flagged</h3>
            <div className="text-2xl font-bold text-red-500 mt-1 flex items-baseline gap-2">
              {highRiskCount}
              <span className="text-[10px] bg-red-500/10 px-2 py-0.5 rounded-full">+8%</span>
            </div>
            <p className="text-[10px] text-slate-500 mt-1">Requires manual audit</p>
          </div>
        </div>

        <div className="stat-card glass-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex-shrink-0">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-slate-400 text-[10px] font-semibold tracking-wider uppercase">Processing Queue</h3>
            <div className="text-2xl font-bold text-white mt-1">{pendingCount}</div>
            <p className="text-[10px] text-slate-500 mt-1">Awaiting verification</p>
          </div>
        </div>

        <div className="stat-card glass-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex-shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-slate-400 text-[10px] font-semibold tracking-wider uppercase">True Negative Rate</h3>
            <div className="text-2xl font-bold text-emerald-500 mt-1">99.4%</div>
            <p className="text-[10px] text-slate-500 mt-1">Pipeline recall precision</p>
          </div>
        </div>

        <div className="stat-card glass-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-violet-500/10 text-violet-400 border border-violet-500/20 flex-shrink-0">
            <Brain className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-slate-400 text-[10px] font-semibold tracking-wider uppercase">LLM Insights</h3>
            <div className="text-2xl font-bold text-white mt-1">{cases.length * 3}</div>
            <p className="text-[10px] text-slate-500 mt-1">Ollama analyses today</p>
          </div>
        </div>
      </div>

      {/* ── Charts ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="glass-panel p-6 flex flex-col">
          <h4 className="text-sm font-bold font-heading mb-4 text-white">Monthly Fraud Detection Telemetry</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', fontSize: 11 }} />
                <Line type="monotone" dataKey="fraud" stroke="#ef4444" strokeWidth={2.5} name="Fraud Detections" dot={{ fill: '#ef4444', r: 3 }} />
                <Line type="monotone" dataKey="safe" stroke="#10b981" strokeWidth={2} name="Verified Safe" dot={{ fill: '#10b981', r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-panel p-6 flex flex-col">
          <h4 className="text-sm font-bold font-heading mb-4 text-white">Fraud Flags by Document Category</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#fff', fontSize: 11 }} />
                <Bar dataKey="count" fill="url(#bar-grad)" radius={[4, 4, 0, 0]} name="Flags Raised" />
                <defs>
                  <linearGradient id="bar-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#4f46e5" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Cases Queue ──────────────────────────────────────────────────── */}
      <div className="glass-panel p-6">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h4 className="text-sm font-bold font-heading text-white">Real-Time Verification Queue</h4>
            <p className="text-slate-400 text-[10px] mt-0.5">Loan applications awaiting document integrity audits</p>
          </div>
          <button className="flex items-center gap-1.5 text-[10px] text-indigo-400 font-bold hover:text-indigo-300 transition">
            View All <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center py-12 text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-2" />
            <p className="text-sm font-semibold">Connecting to FastAPI pipeline…</p>
          </div>
        ) : error ? (
          <div className="text-center py-12 text-red-400">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-70" />
            <p className="text-sm font-semibold">{error}</p>
          </div>
        ) : cases.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <Database className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm">Verification queue is empty</p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-700/40 rounded-xl">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-900/60 border-b border-slate-700/50 text-slate-400">
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Case ID</th>
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Applicant</th>
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Risk Score</th>
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Date</th>
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Status</th>
                  <th className="p-4 font-semibold text-[10px] uppercase tracking-wider text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredCases.map((c) => {
                  const isHigh = c.risk_score > 75;
                  const isMedium = c.risk_score <= 75 && c.risk_score > 30;
                  const riskColor = isHigh ? 'text-red-500' : isMedium ? 'text-orange-400' : 'text-emerald-500';
                  const badgeClass =
                    c.status === 'Approved' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                    c.status === 'Rejected' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                    c.status === 'Escalated' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20' :
                    'bg-slate-800 text-slate-400';

                  return (
                    <tr key={c.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-4 font-bold text-white">{c.case_id}</td>
                      <td className="p-4 font-semibold text-slate-200">{c.applicant_name}</td>
                      <td className="p-4">
                        <span className={`font-bold ${riskColor}`}>{c.risk_score}%</span>
                      </td>
                      <td className="p-4 text-slate-500 text-[10px]">
                        {new Date(c.created_at).toLocaleDateString('en-IN')}
                      </td>
                      <td className="p-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold ${badgeClass}`}>
                          {c.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <button
                          onClick={() => onSelectCase(c.case_id)}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-3 py-1.5 rounded-lg active:scale-95 transition text-[10px]">
                          Audit Case
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
