import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  FileText, AlertTriangle, CheckCircle2, XCircle,
  RefreshCw, Network, ShieldCheck, Building2, CreditCard, ExternalLink, Download
} from 'lucide-react';

/* ── Tiny SVG Fraud Ring Graph ─────────────────────────────────────────────── */
const FraudRingGraph = ({ graphData }) => {
  const svgRef = useRef(null);
  if (!graphData || !graphData.nodes?.length) return null;

  const W = 320, H = 220;
  const nodes = graphData.nodes.slice(0, 20);
  const edges = graphData.edges.slice(0, 30);

  // Simple circular layout
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
    const r = Math.min(W, H) * 0.38;
    positions[n.id] = {
      x: W / 2 + r * Math.cos(angle),
      y: H / 2 + r * Math.sin(angle),
    };
  });

  return (
    <svg width={W} height={H} className="mx-auto block" viewBox={`0 0 ${W} ${H}`}>
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      {edges.map((e, i) => {
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return null;
        return (
          <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
            stroke="#334155" strokeWidth="1.5" opacity="0.6" />
        );
      })}
      {nodes.map((n) => {
        const p = positions[n.id];
        if (!p) return null;
        const iconMap = { applicant: '👤', employer: '🏢', pan: '🪪' };
        return (
          <g key={n.id} filter={n.suspicious ? 'url(#glow)' : undefined}>
            <circle cx={p.x} cy={p.y} r={n.suspicious ? 10 : 7}
              fill={n.color} opacity={0.9}
              stroke={n.suspicious ? '#ef4444' : 'transparent'} strokeWidth="2" />
            <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize="7"
              fill="white" fontWeight="bold">
              {iconMap[n.type] || '?'}
            </text>
            <text x={p.x} y={p.y + 18} textAnchor="middle" fontSize="6.5"
              fill={n.suspicious ? '#fca5a5' : '#94a3b8'} fontWeight={n.suspicious ? 'bold' : 'normal'}>
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

/* ── External Verify Badge ─────────────────────────────────────────────────── */
const VerifyBadge = ({ data }) => {
  if (!data) return <span className="text-slate-600 text-[9px]">N/A</span>;
  const isMock = data.mock;
  const isVerified = data.verified || data.registered;

  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold border
      ${isVerified ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
        isVerified === false ? 'bg-red-500/10 text-red-400 border-red-500/20' :
        'bg-slate-700/50 text-slate-500 border-slate-700'}`}>
      {isVerified ? <CheckCircle2 className="w-2.5 h-2.5" /> : isVerified === false ? <XCircle className="w-2.5 h-2.5" /> : null}
      {data.source}{isMock ? ' (Mock)' : ''}
      {isVerified ? ' ✓' : isVerified === false ? ' ✗' : ' ?'}
    </div>
  );
};

const CrossDoc = () => {
  const [files, setFiles] = useState({ bank: null, income: null, itr: null });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);

  const loadPreset = (slot, file, name) => {
    setFiles(prev => ({ ...prev, [slot]: { filename: name, presetPath: file } }));
  };

  const handleVerify = async () => {
    if (!files.bank || !files.income) {
      alert('Load Bank Statement and Salary Slip to proceed.');
      return;
    }
    setLoading(true);
    setResults(null);
    try {
      const form = new FormData();
      
      // Load or append bank statement
      if (files.bank.presetPath) {
        const bankBlob = await fetch(`/samples/${files.bank.presetPath}`).then(r => r.blob());
        form.append('bank_stmt', new File([bankBlob], files.bank.filename));
      } else {
        form.append('bank_stmt', files.bank.fileObj);
      }
      
      // Load or append salary slip
      if (files.income.presetPath) {
        const salBlob = await fetch(`/samples/${files.income.presetPath}`).then(r => r.blob());
        form.append('salary_slip', new File([salBlob], files.income.filename));
      } else {
        form.append('salary_slip', files.income.fileObj);
      }
      
      // Load or append ITR if present
      if (files.itr) {
        if (files.itr.presetPath) {
          const itrBlob = await fetch(`/samples/${files.itr.presetPath}`).then(r => r.blob());
          form.append('itr', new File([itrBlob], files.itr.filename));
        } else {
          form.append('itr', files.itr.fileObj);
        }
      }

      const res = await axios.post('/api/cross-verify', form);
      setResults(res.data);
      loadFraudGraph();
    } catch (err) {
      alert('Cross verify error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const loadFraudGraph = async () => {
    setGraphLoading(true);
    try {
      const res = await axios.get('/api/graph-analysis/SP-29402');
      setGraphData(res.data);
    } catch (_) {}
    finally { setGraphLoading(false); }
  };

  const handleDownloadCSV = () => {
    if (!results || !results.matrix) return;
    const headers = ["Check Field", "Bank Statement Value", "Salary Slip Value", "ITR-V Value", "Confidence", "Status", "Notes"];
    const rows = results.matrix.map(row => [
      row.field,
      row.bank_val,
      row.sal_val,
      row.itr_val,
      row.confidence || "—",
      row.is_match ? "PASS" : "FAIL",
      row.note
    ]);
    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(","), ...rows.map(e => e.map(val => `"${String(val).replace(/"/g, '""')}"`).join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Cross_Verify_Report_${files.bank?.filename || "Document"}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const statusConfig = results ? (
    results.overall_status.includes('CRITICAL') ? {
      cls: 'bg-red-500/10 text-red-400 border border-red-500/20',
      icon: <AlertTriangle className="w-4 h-4 text-red-500" />,
    } : results.overall_status.includes('INCONSISTENCIES') ? {
      cls: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      icon: <AlertTriangle className="w-4 h-4 text-orange-500" />,
    } : {
      cls: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      icon: <ShieldCheck className="w-4 h-4 text-emerald-500" />,
    }
  ) : null;

  return (
    <div className="space-y-8 animate-fadeIn">

      {/* Document Slots */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[
          { slot: 'bank', label: 'Bank Statement', num: 1, preset: 'sample_genuine.pdf', name: 'hdfc_bank_statement.pdf', period: 'HDFC · Nov 2025' },
          { slot: 'income', label: 'Salary Slip', num: 2, preset: 'sample_tampered.pdf', name: 'salary_slip_november.pdf', period: 'Apex Tech · Nov 2025' },
          { slot: 'itr', label: 'ITR-V Return', num: 3, preset: 'sample_genuine.pdf', name: 'itr_acknowledgement.pdf', period: 'AY 2025–26 · Optional' },
        ].map(({ slot, label, num, preset, name, period }) => (
          <div key={slot} className="glass-panel p-5 flex flex-col justify-between min-h-[180px]">
            <div>
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
                <span className="w-5 h-5 bg-indigo-600/20 border border-indigo-500/30 rounded-full flex items-center justify-center text-[9px] font-bold text-indigo-400">{num}</span>
                <h5 className="text-[10px] font-bold text-white uppercase tracking-wider">{label}</h5>
              </div>
              {files[slot] ? (
                <div className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-xl flex items-center gap-3">
                  <FileText className="w-7 h-7 text-emerald-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-white truncate">{files[slot].filename}</p>
                    <p className="text-[10px] text-slate-500">
                      {files[slot].fileObj 
                        ? `${(files[slot].fileObj.size / 1024).toFixed(1)} KB · Custom`
                        : period
                      }
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-slate-600 text-[10px] py-2">No document loaded</p>
              )}
            </div>
            {!files[slot] && (
              <div className="space-y-2 mt-3">
                <button onClick={() => loadPreset(slot, preset, name)}
                  className="w-full bg-slate-900 hover:bg-slate-800 border border-slate-700/60 text-slate-300 font-bold py-2 rounded-xl text-[10px] active:scale-95 transition">
                  Load preset
                </button>
                <div className="relative">
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        const file = e.target.files[0];
                        setFiles(prev => ({
                          ...prev,
                          [slot]: { filename: file.name, fileObj: file }
                        }));
                      }
                    }}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <button
                    className="w-full bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 text-indigo-400 font-bold py-2 rounded-xl text-[10px] active:scale-95 transition">
                    Upload custom file
                  </button>
                </div>
              </div>
            )}
            {files[slot] && (
              <button onClick={() => setFiles(p => ({ ...p, [slot]: null }))}
                className="w-full bg-slate-900/40 hover:bg-slate-800 border border-slate-700/30 text-slate-500 font-semibold py-1.5 rounded-xl text-[9px] active:scale-95 transition mt-3">
                Clear
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="flex justify-center">
        <button onClick={handleVerify} disabled={loading || !files.bank || !files.income}
          className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-extrabold px-8 py-3.5 rounded-xl shadow-lg shadow-indigo-500/20 active:scale-95 transition flex items-center gap-2 text-sm disabled:opacity-40">
          {loading ? <><RefreshCw className="w-4 h-4 animate-spin" />Reconciling…</> : '▶ Run Cross-Document Consistency Check'}
        </button>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-6 animate-fadeIn">
          {/* Header */}
          <div className="glass-panel p-5">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                {statusConfig?.icon}
                <div>
                  <h4 className="text-sm font-bold text-white">Cross-Document Verification Matrix</h4>
                  <p className="text-slate-400 text-[10px] mt-0.5">
                    {results.passed}/{results.total_checks} checks passed
                    {results.failed > 0 && <span className="text-red-400 font-bold ml-2">· {results.failed} conflict{results.failed > 1 ? 's' : ''} detected</span>}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleDownloadCSV}
                  className="bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 text-indigo-400 font-bold py-1.5 px-3 rounded-xl text-[10px] active:scale-95 transition flex items-center gap-1.5 no-print">
                  <Download className="w-3.5 h-3.5" />
                  Download CSV Report
                </button>
                <span className={`px-3 py-1.5 rounded-lg text-[10px] font-bold ${statusConfig?.cls}`}>
                  {results.overall_status}
                </span>
              </div>
            </div>
          </div>

          {/* Diff Table */}
          <div className="glass-panel p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-900/60 border-b border-slate-700/50 text-slate-400">
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Check</th>
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Bank Statement</th>
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Salary Slip</th>
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">ITR-V</th>
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider">Confidence</th>
                    <th className="p-4 font-semibold text-[10px] uppercase tracking-wider text-right">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {results.matrix.map((row, idx) => (
                    <tr key={idx}
                      className={`transition hover:bg-slate-800/20 ${!row.is_match ? 'bg-red-950/15' : 'bg-emerald-950/5'}`}>
                      <td className="p-4">
                        <div className="font-bold text-white text-[11px]">{row.field}</div>
                        <div className={`text-[10px] mt-1 leading-relaxed ${!row.is_match ? 'text-red-400' : 'text-slate-500'}`}>
                          {row.note}
                        </div>
                        {/* External verify badge */}
                        {row.external && (
                          <div className="mt-1.5">
                            <VerifyBadge data={row.external} />
                          </div>
                        )}
                      </td>
                      <td className={`p-4 text-[11px] ${!row.is_match ? 'text-red-300 font-semibold' : 'text-slate-300'} max-w-[160px]`}>
                        <span className="line-clamp-3">{row.bank_val}</span>
                      </td>
                      <td className={`p-4 text-[11px] ${!row.is_match ? 'text-red-300 font-semibold' : 'text-slate-300'} max-w-[160px]`}>
                        <span className="line-clamp-3">{row.sal_val}</span>
                      </td>
                      <td className="p-4 text-[11px] text-slate-500 max-w-[120px]">
                        <span className="line-clamp-2">{row.itr_val}</span>
                      </td>
                      <td className="p-4">
                        <span className="text-[10px] font-bold text-slate-500">{row.confidence || '—'}</span>
                      </td>
                      <td className="p-4 text-right">
                        {row.is_match
                          ? <CheckCircle2 className="w-5 h-5 text-emerald-500 ml-auto" />
                          : <XCircle className="w-5 h-5 text-red-500 ml-auto" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Fraud Ring Graph Panel */}
          {(graphData || graphLoading) && (
            <div className="glass-panel p-5">
              <div className="flex items-center gap-2 mb-4">
                <Network className="w-4 h-4 text-orange-400" />
                <h4 className="text-sm font-bold text-white">Fraud Ring Graph Analysis</h4>
                {graphData?.fraud_ring_detected && (
                  <span className="px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded text-[9px] font-bold">
                    RING DETECTED — {graphData.ring_size} entities
                  </span>
                )}
              </div>

              {graphLoading ? (
                <div className="flex items-center justify-center py-8 text-slate-500">
                  <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                  <span className="text-xs">Building fraud graph…</span>
                </div>
              ) : graphData ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* SVG Graph */}
                  <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                    <FraudRingGraph graphData={graphData.graph_data} />
                    <div className="flex items-center justify-center gap-4 mt-2">
                      {[
                        { color: '#6366f1', label: 'Applicant' },
                        { color: '#f59e0b', label: 'Employer' },
                        { color: '#10b981', label: 'PAN Node' },
                      ].map(({ color, label }) => (
                        <div key={label} className="flex items-center gap-1.5">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                          <span className="text-[9px] text-slate-500">{label}</span>
                        </div>
                      ))}
                      <div className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                        <span className="text-[9px] text-slate-500">Suspicious</span>
                      </div>
                    </div>
                  </div>

                  {/* Suspicious entities list */}
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold uppercase text-slate-500 tracking-wider">
                      Shared Entities ({graphData.shared_entities?.length || 0})
                    </p>
                    {graphData.shared_entities?.length > 0 ? (
                      graphData.shared_entities.map((e, i) => (
                        <div key={i} className={`p-3 rounded-xl border text-[10px]
                          ${e.risk === 'CRITICAL' ? 'bg-red-500/8 border-red-500/20' : 'bg-orange-500/8 border-orange-500/20'}`}>
                          <div className="flex items-center gap-2">
                            {e.entity_type === 'Employer' ? <Building2 className="w-3.5 h-3.5 text-amber-500" /> : <CreditCard className="w-3.5 h-3.5 text-indigo-400" />}
                            <span className={`font-bold ${e.risk === 'CRITICAL' ? 'text-red-400' : 'text-orange-400'}`}>{e.entity}</span>
                            <span className={`ml-auto px-1.5 py-0.5 rounded text-[8px] font-bold
                              ${e.risk === 'CRITICAL' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'}`}>
                              {e.risk}
                            </span>
                          </div>
                          <p className="text-slate-500 mt-1">{e.entity_type} · appears in {e.appearances} applications</p>
                          {e.note && <p className="text-slate-600 mt-0.5 text-[9px]">{e.note}</p>}
                        </div>
                      ))
                    ) : (
                      <div className="flex items-center gap-2 p-3 bg-emerald-500/5 border border-emerald-500/15 rounded-xl">
                        <ShieldCheck className="w-4 h-4 text-emerald-500" />
                        <p className="text-emerald-400 text-[10px]">No shared entities detected across cases</p>
                      </div>
                    )}
                    <p className="text-[9px] text-slate-600 mt-2">
                      Graph: {graphData.total_nodes} nodes · {graphData.total_edges} edges
                    </p>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* Conflict Warning */}
          {results.failed > 0 && (
            <div className="p-4 bg-red-950/20 border border-red-500/20 rounded-xl flex gap-3">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <h5 className="text-xs font-bold text-red-400">Fraud Risk: {results.failed} Inconsistencies Found</h5>
                <p className="text-slate-300 text-[10px] leading-relaxed mt-1">
                  {results.failed} cross-document field{results.failed > 1 ? 's' : ''} failed consistency checks.
                  Red rows in the matrix above indicate specific conflicts.
                  Common fraud pattern: income inflation by overwriting the leading digit in Net Pay field
                  (e.g. ₹1,33,000 → ₹2,33,000) while bank statement retains the original deposit amount.
                </p>
                <a href="https://mca.gov.in/content/mca/global/en/mca/master-data/MDS.html"
                  target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[9px] text-indigo-400 hover:text-indigo-300 mt-2 font-semibold">
                  <ExternalLink className="w-3 h-3" />
                  Verify employer at mca.gov.in
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CrossDoc;
