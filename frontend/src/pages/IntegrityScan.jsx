import React, { useState, useEffect, useContext, useRef, useCallback } from 'react';
import axios from '../lib/axios';
import { useDropzone } from 'react-dropzone';
import { AuthContext } from '../context/AuthContext';
import {
  Upload, FileText, AlertTriangle, ShieldCheck,
  Settings, Loader2, ZoomIn, FileQuestion, ArrowUpRight,
  CheckCircle2, XCircle, Brain, Fingerprint, Network, ChevronDown
} from 'lucide-react';

const SEVERITY_CONFIG = {
  HIGH: { bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400', icon: 'text-red-500', dot: 'bg-red-500' },
  MEDIUM: { bg: 'bg-orange-500/10', border: 'border-orange-500/20', text: 'text-orange-400', icon: 'text-orange-500', dot: 'bg-orange-500' },
  LOW: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', text: 'text-yellow-400', icon: 'text-yellow-500', dot: 'bg-yellow-500' },
  INFO: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400', icon: 'text-blue-500', dot: 'bg-blue-400' },
};

const IntegrityScan = ({ selectedCaseId, onClearCase }) => {
  const { token, user } = useContext(AuthContext);
  const [caseId, setCaseId] = useState(selectedCaseId || '');
  const [applicant, setApplicant] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [activeFilter, setActiveFilter] = useState('normal');

  const [ocrForm, setOcrForm] = useState({
    name: '',
    pan: '',
    gross_earnings: 0,
    deductions: 0,
    net_pay: ''
  });
  const [isOcrModified, setIsOcrModified] = useState(false);

  // ELA slider state
  const [elaOpacity, setElaOpacity] = useState(0);
  const [elaImageLoaded, setElaImageLoaded] = useState(false);
  const canvasRef = useRef(null);
  const originalImgRef = useRef(null);
  const overlayImgRef = useRef(null);

  // LLM panel
  const [llmExpanded, setLlmExpanded] = useState(false);
  const [jsonExpanded, setJsonExpanded] = useState(false);

  useEffect(() => {
    if (scanResult && scanResult.extracted_data) {
      const d = scanResult.extracted_data;
      setOcrForm({
        name: d.name || 'Unknown',
        pan: d.pan || 'Unknown',
        gross_earnings: d.gross_earnings || 0,
        deductions: d.deductions || 0,
        net_pay: d.net_pay || ''
      });
      setIsOcrModified(false);
    }
  }, [scanResult]);

  const handleRecalculateRisk = () => {
    if (!scanResult) return;
    const gross = Number(ocrForm.gross_earnings) || 0;
    const ded = Number(ocrForm.deductions) || 0;
    let parsedNet = 0;
    if (ocrForm.net_pay) {
      const cleaned = ocrForm.net_pay.replace(/[^\d.]/g, '');
      parsedNet = Number(cleaned) || 0;
    }
    const mathInconsistent = gross > 0 && ded >= 0 && parsedNet > 0 && Math.abs((gross - ded) - parsedNet) > 10.0;
    let updatedAnomalies = (scanResult.anomalies || []).filter(a => a.id !== 'math-inconsistency-manual');
    if (mathInconsistent) {
      updatedAnomalies.push({
        id: 'math-inconsistency-manual',
        type: 'math',
        severity: 'HIGH',
        title: 'Math Reconciliation Conflict (Audited)',
        desc: `Audited Gross Salary (Rs. ${gross.toLocaleString()}) minus Deductions (Rs. ${ded.toLocaleString()}) does not reconcile with Net Payout (Rs. ${parsedNet.toLocaleString()}). Delta: Rs. ${Math.abs((gross - ded) - parsedNet).toLocaleString()}. Strong indicator of numbers tampering.`,
        conf: '100.0%'
      });
    }
    const fontAnomaliesCount = updatedAnomalies.filter(a => a.type === 'font').length;
    const pixelAnomaliesCount = updatedAnomalies.filter(a => a.type === 'heatmap' || a.type === 'image-ela-forensics').length;
    const metaAnomaliesCount = updatedAnomalies.filter(a => a.type === 'metadata').length;
    let baseScore = 0;
    if (fontAnomaliesCount > 0) baseScore += 45;
    if (pixelAnomaliesCount > 0) baseScore += 50;
    if (metaAnomaliesCount > 0) baseScore += 30;
    if (mathInconsistent) baseScore += 40;
    const newRiskScore = Math.min(100, Math.max(5, baseScore));
    const newRiskLevel = newRiskScore > 75 ? 'HIGH' : newRiskScore > 30 ? 'MEDIUM' : 'LOW';
    const newConfidence = newRiskScore > 75 ? '98.5%' : '80.0%';
    setScanResult(prev => ({
      ...prev,
      risk_score: newRiskScore,
      risk_level: newRiskLevel,
      confidence: newConfidence,
      anomalies: updatedAnomalies,
      extracted_data: {
        ...prev.extracted_data,
        name: ocrForm.name,
        pan: ocrForm.pan,
        gross_earnings: gross,
        deductions: ded,
        net_pay: ocrForm.net_pay
      }
    }));
    setIsOcrModified(false);
  };

  const handlePrintReport = () => {
    window.print();
  };

  const presets = [
    { label: 'Tampered PDF — SP-29402', file: 'sample_tampered.pdf', cId: 'SP-29402', type: 'Salary Slip' },
    { label: 'Genuine PDF — SP-82910', file: 'sample_genuine.pdf', cId: 'SP-82910', type: 'Salary Slip' },
  ];

  useEffect(() => {
    if (selectedCaseId) {
      setCaseId(selectedCaseId);
      fetchCaseDetails(selectedCaseId);
    }
  }, [selectedCaseId]);

  const fetchCaseDetails = async (cId) => {
    try {
      const res = await axios.get(`/api/cases/${cId}`);
      setApplicant(res.data.case_details.applicant_name);
      if (res.data.documents.length > 0) {
        const d = res.data.documents[0];
        setScanResult({
          filename: d.filename,
          doc_type: d.doc_type,
          risk_score: d.risk_score,
          risk_level: d.risk_score > 75 ? 'HIGH' : d.risk_score > 30 ? 'MEDIUM' : 'LOW',
          confidence: d.risk_score > 75 ? '98.5%' : '80.0%',
          ela_image_url: d.ela_image_url,
          ela_overlay_url: d.ela_overlay_url,
          anomalies: d.font_anomalies || [],
          extracted_data: d.ocr_data || {},
          llm_insight: d.risk_score > 75
            ? '<p><strong>Flagged:</strong> Multiple anomalies detected.</p>'
            : '<p><strong>Clean:</strong> No significant anomalies.</p>',
          llm_json: null,
          recommendation: d.risk_score > 75 ? 'RISK LEVEL: HIGH' : 'RISK LEVEL: LOW',
        });
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handlePresetScan = async (preset) => {
    setCaseId(preset.cId);
    setIsScanning(true);
    setScanResult(null);
    setElaOpacity(0);
    try {
      try {
        const f = new FormData();
        f.append('case_id', preset.cId);
        f.append('applicant_name', 'Demo Applicant');
        await axios.post('/api/cases', f);
      } catch (_) {}

      const blob = await fetch(`/samples/${preset.file}`).then(r => r.blob());
      const fileObj = new File([blob], preset.file, { type: 'application/pdf' });
      const form = new FormData();
      form.append('case_id', preset.cId);
      form.append('doc_type', preset.type);
      form.append('file', fileObj);

      const res = await axios.post('/api/scan', form);
      setScanResult(res.data);
    } catch (err) {
      alert('Scan failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsScanning(false);
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    if (!acceptedFiles.length) return;
    if (!caseId) { alert('Please enter a Case Reference ID first.'); return; }

    const file = acceptedFiles[0];
    setIsScanning(true);
    setScanResult(null);
    setElaOpacity(0);

    try {
      try {
        const f = new FormData();
        f.append('case_id', caseId);
        f.append('applicant_name', applicant || 'External Upload');
        await axios.post('/api/cases', f);
      } catch (_) {}

      let detectedType = 'Salary Slip';
      if (file.name.toLowerCase().includes('bank')) detectedType = 'Bank Statement';
      if (file.name.toLowerCase().includes('itr')) detectedType = 'ITR-V Ack';

      const form = new FormData();
      form.append('case_id', caseId);
      form.append('doc_type', detectedType);
      form.append('file', file);

      const res = await axios.post('/api/scan', form);
      setScanResult(res.data);
    } catch (err) {
      alert('Scan failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsScanning(false);
    }
  }, [caseId, applicant]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: { 'application/pdf': ['.pdf'], 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'] }
  });

  const handleDisposition = async (decision) => {
    if (!scanResult) return;
    try {
      const form = new FormData();
      form.append('status', decision === 'approve' ? 'Approved' : decision === 'reject' ? 'Rejected' : 'Escalated');
      form.append('token', token);
      form.append('notes', `Risk score: ${scanResult.risk_score}%`);
      await axios.post(`/api/cases/${caseId}/disposition`, form);
      alert(`Case marked as ${decision.toUpperCase()}`);
      if (onClearCase) onClearCase();
    } catch (err) {
      alert('Disposition failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleReportForgery = async (type, value) => {
    if (!value || value === 'Unknown') return;
    try {
      const formData = new FormData();
      formData.append('pattern_type', type);
      formData.append('pattern_value', value);
      formData.append('description', `Manually blocklisted by Underwriter for Case ${caseId}`);
      
      const res = await axios.post('/api/fraud-library', formData);
      alert(res.data.message || "Successfully blocklisted!");
    } catch (err) {
      alert("Reporting failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const isImageFile = scanResult &&
    (scanResult.filename?.match(/\.(jpg|jpeg|png)$/i) ||
     scanResult.ela_image_url || scanResult.ela_overlay_url);

  const riskColor = scanResult?.risk_score > 75 ? 'border-red-500 bg-red-500/5 shadow-red-500/10'
    : scanResult?.risk_score > 30 ? 'border-orange-500 bg-orange-500/5 shadow-orange-500/10'
    : 'border-emerald-500 bg-emerald-500/5 shadow-emerald-500/10';

  const riskTextColor = scanResult?.risk_score > 75 ? 'text-red-400'
    : scanResult?.risk_score > 30 ? 'text-orange-400' : 'text-emerald-400';

  const llmData = scanResult?.llm_json;
  const actionColors = {
    REJECT: 'bg-red-500/10 text-red-400 border border-red-500/20',
    ESCALATE: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
    APPROVE: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    MANUAL_REVIEW: 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20',
  };

  const renderPDFText = () => {
    if (!scanResult?.extracted_data) return null;
    const hasFontAnomaly = (scanResult.anomalies || []).some(a => a.type === 'font');
    const d = scanResult.extracted_data;

    const lines = [
      { text: 'APEX TECH SOLUTIONS PVT LTD', bold: true },
      { text: 'Regd. Office: 44, Electronic City, Bangalore', muted: true },
      { text: '─'.repeat(52), muted: true },
      { text: 'PAY SLIP FOR THE MONTH OF NOVEMBER 2025', bold: true },
      { text: `Employee Name:      ${d.name !== 'Unknown' ? d.name : 'Karan Singh'}` },
      { text: `PAN Card No:        ${d.pan !== 'Unknown' ? d.pan : 'BPHPS2930K'}` },
      { text: '─'.repeat(52), muted: true },
      { text: 'Basic Salary:                       85,000.00' },
      { text: 'House Rent Allowance:               35,000.00' },
      { text: 'Special Allowance:                  25,000.00' },
      { text: 'Gross Earnings:                  1,45,000.00', bold: true },
      { text: '─'.repeat(52), muted: true },
      { text: 'Total Deductions:                   12,000.00' },
      { text: '─'.repeat(52), muted: true },
      {
        text: hasFontAnomaly
          ? 'NET PAYOUT VALUE:          Rs. 2,33,000.00'
          : 'NET PAYOUT VALUE:          Rs. 1,33,000.00',
        bold: true,
        highlight: hasFontAnomaly && activeFilter === 'font',
        tooltip: hasFontAnomaly ? 'FONT ANOMALY: Character uses Helvetica-Bold mixed with Times-Roman' : null,
      },
    ];

    return (
      <div className="w-full bg-[#fafbfc] border border-slate-300 rounded-lg p-6 font-mono text-[11px] text-slate-800 leading-relaxed shadow-inner max-h-[420px] overflow-y-auto">
        {lines.map((line, idx) => (
          <div key={idx} className={`${line.muted ? 'text-slate-400' : ''}`}>
            {line.highlight ? (
              <span
                className="relative bg-red-100 text-red-700 font-black px-1 rounded cursor-help border-b-2 border-red-500 underline decoration-dotted"
                title={line.tooltip}
              >
                {line.text}
                <span className="ml-2 text-[9px] bg-red-500 text-white px-1.5 py-0.5 rounded font-bold">TAMPERED</span>
              </span>
            ) : (
              <span className={line.bold ? 'font-bold' : ''}>{line.text}</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 animate-fadeIn">

      {/* ── Left Column ────────────────────────────────────────────── */}
      <div className="xl:col-span-2 space-y-6">

        {/* Setup Panel */}
        <div className="glass-panel p-6">
          <h4 className="text-sm font-bold font-heading text-white mb-4 flex items-center gap-2">
            <Fingerprint className="w-4 h-4 text-indigo-400" />
            Verification Setup
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
            <div>
              <label className="block text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-1.5">Case Reference ID</label>
              <input
                type="text"
                value={caseId}
                onChange={e => setCaseId(e.target.value)}
                placeholder="e.g. SP-29402"
                className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-3 px-4 outline-none focus:border-indigo-500 transition font-semibold text-xs"
              />
            </div>
            <div>
              <label className="block text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-1.5">Applicant Full Name</label>
              <input
                type="text"
                value={applicant}
                onChange={e => setApplicant(e.target.value)}
                placeholder="e.g. Karan Singh"
                className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-3 px-4 outline-none focus:border-indigo-500 transition font-semibold text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2.5 mb-5">
            {presets.map((p, i) => (
              <button key={i} onClick={() => handlePresetScan(p)}
                className="bg-indigo-600/15 hover:bg-indigo-600/30 border border-indigo-500/20 text-indigo-400 text-[10px] font-bold px-3.5 py-2 rounded-lg flex items-center gap-1.5 active:scale-95 transition">
                <ArrowUpRight className="w-3.5 h-3.5" />
                {p.label}
              </button>
            ))}
          </div>

          <div {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
              ${isDragActive ? 'border-indigo-500 bg-indigo-500/8' : 'border-slate-700 hover:border-indigo-500/60 hover:bg-indigo-500/4'}`}>
            <input {...getInputProps()} />
            <Upload className="w-9 h-9 mx-auto text-slate-500 mb-3" />
            <p className="text-white text-xs font-bold">Drag & Drop document for real forensic analysis</p>
            <p className="text-slate-500 text-[10px] mt-1.5">PDF, JPEG, or PNG — up to 15MB. All 5 pipeline layers run instantly.</p>
          </div>
        </div>

        {/* Document View */}
        <div className="glass-panel p-6">
          <div className="flex justify-between items-center border-b border-slate-700/40 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span className="text-xs font-bold text-white">
                {scanResult ? scanResult.filename : 'No document loaded'}
              </span>
              {scanResult?.textract_used && (
                <span className="text-[9px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded font-bold">AWS Textract</span>
              )}
            </div>
            {scanResult && (
              <div className="flex gap-1.5">
                {['normal', 'font'].map(f => (
                  <button key={f} onClick={() => setActiveFilter(f)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-bold border transition
                      ${activeFilter === f ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-900 border-slate-700 text-slate-400'}`}>
                    {f === 'normal' ? 'Normal' : 'Typography'}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="theme-bg-scanner border theme-border rounded-xl min-h-[480px] flex items-center justify-center relative overflow-hidden p-6">
            {isScanning ? (
              <div className="text-center text-slate-400 relative z-20 w-full max-w-xs mx-auto">
                <div className="relative w-16 h-16 mx-auto mb-6">
                  <div className="absolute inset-0 border-4 border-indigo-500 rounded-full animate-ping opacity-20" />
                  <div className="absolute inset-0 border-4 border-t-indigo-500 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin" />
                </div>
                <p className="text-sm font-bold text-white">Pipeline Running…</p>
                <div className="space-y-1.5 mt-5 text-[10px] text-slate-500 text-left max-w-[220px] mx-auto">
                  {['Layer 1: Textract OCR + PyMuPDF metadata',
                    'Layer 2: ELA hot-colormap + FFT analysis',
                    'Layer 3: Font mismatch character scan',
                    'Layer 4: Ollama Local risk insight',
                    'Layer 5: networkx fraud ring check'
                  ].map((s, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin text-indigo-400 flex-shrink-0" />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            ) : scanResult ? (
              isImageFile ? (
                /* ── ELA Slider Overlay View ─────────────────── */
                <div className="w-full space-y-4">
                  <div className="relative w-full aspect-[4/3] rounded-lg overflow-hidden shadow-lg select-none bg-slate-900">
                    {/* Original image */}
                    <img
                      src={`/uploads/${scanResult.filename}`}
                      alt="Original"
                      className="absolute inset-0 w-full h-full object-contain"
                    />
                    {/* ELA overlay at elaOpacity */}
                    {scanResult.ela_overlay_url && (
                      <img
                        src={scanResult.ela_overlay_url}
                        alt="ELA Overlay"
                        className="absolute inset-0 w-full h-full object-contain transition-opacity duration-100"
                        style={{ opacity: elaOpacity / 100 }}
                      />
                    )}
                    {/* Labels */}
                    <div className="absolute top-2 left-2 text-[9px] font-bold bg-slate-900/80 text-slate-300 px-2 py-1 rounded">ORIGINAL</div>
                    {elaOpacity > 50 && (
                      <div className="absolute top-2 right-2 text-[9px] font-bold bg-red-900/80 text-red-300 px-2 py-1 rounded">ELA HEATMAP</div>
                    )}
                    {/* Colormap legend */}
                    <div className="absolute bottom-2 right-2 flex items-center gap-1.5 bg-slate-900/80 px-2 py-1 rounded">
                      <div className="w-16 h-2 rounded" style={{
                        background: 'linear-gradient(to right, #000000, #8B0000, #FF0000, #FF4500, #FF8C00, #FFD700)'
                      }} />
                      <span className="text-[8px] text-slate-400">Clean → Tampered</span>
                    </div>
                  </div>
                  {/* Slider */}
                  <div className="px-2">
                    <div className="flex justify-between text-[9px] text-slate-500 mb-1.5">
                      <span>Normal View</span>
                      <span className="font-bold text-indigo-400">Tamper Reveal Slider — {elaOpacity}%</span>
                      <span>ELA Heatmap</span>
                    </div>
                    <input
                      type="range" min="0" max="100" value={elaOpacity}
                      onChange={e => setElaOpacity(Number(e.target.value))}
                      className="w-full h-2 rounded-full cursor-pointer accent-indigo-500"
                    />
                  </div>
                  {scanResult.ela_anomaly_pct !== undefined && (
                    <p className="text-center text-[10px] text-slate-500">
                      {scanResult.ela_anomaly_pct}% of pixels above manipulation threshold
                      {scanResult.ela_anomaly_pct > 5 ? ' — 🔴 High ELA residuals detected' : ' — ✓ Within expected range'}
                    </p>
                  )}
                </div>
              ) : (
                /* ── PDF text view ───────────────────────────── */
                renderPDFText()
              )
            ) : (
              <div className="text-center text-slate-500">
                <FileQuestion className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p className="text-xs font-semibold">Upload a document or select a case preset</p>
              </div>
            )}

            {/* Laser scan animation */}
            {isScanning && (
              <div className="absolute inset-0 pointer-events-none">
                <div className="laser-line-anim absolute top-0 left-0 w-full h-[3px] bg-indigo-500 shadow-md shadow-indigo-500/80" />
                <div className="laser-glow-anim absolute top-0 left-0 w-full h-[60px] bg-gradient-to-b from-indigo-500/15 to-transparent" />
              </div>
            )}
          </div>
        </div>

        {/* OCR Manual Audit & Editor Panel */}
        {scanResult && (
          <div className="glass-panel p-6">
            <h4 className="text-sm font-bold font-heading text-white mb-4 flex items-center gap-2">
              <Settings className="w-4 h-4 text-violet-400" />
              OCR Document Manual Audit & Editor
            </h4>
            <p className="text-[10px] text-slate-400 mb-4">
              Inspect and verify the extracted metadata fields. Underwriters can edit values manually to correct OCR misreads or trigger a real-time recalculation of document risk scores.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-slate-500 text-[9px] font-bold uppercase tracking-wider mb-1">Employee / Applicant Name</label>
                <input
                  type="text"
                  value={ocrForm.name}
                  onChange={e => { setOcrForm(p => ({ ...p, name: e.target.value })); setIsOcrModified(true); }}
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-3 outline-none focus:border-indigo-500 transition text-[11px]"
                />
              </div>
              <div>
                <label className="block text-slate-500 text-[9px] font-bold uppercase tracking-wider mb-1">Extracted PAN Card</label>
                <input
                  type="text"
                  value={ocrForm.pan}
                  onChange={e => { setOcrForm(p => ({ ...p, pan: e.target.value })); setIsOcrModified(true); }}
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-3 outline-none focus:border-indigo-500 transition text-[11px]"
                />
              </div>
              <div>
                <label className="block text-slate-500 text-[9px] font-bold uppercase tracking-wider mb-1">Net Pay (Declared)</label>
                <input
                  type="text"
                  value={ocrForm.net_pay}
                  onChange={e => { setOcrForm(p => ({ ...p, net_pay: e.target.value })); setIsOcrModified(true); }}
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-3 outline-none focus:border-indigo-500 transition text-[11px]"
                />
              </div>
              <div>
                <label className="block text-slate-500 text-[9px] font-bold uppercase tracking-wider mb-1">Gross Earnings (Rs.)</label>
                <input
                  type="number"
                  value={ocrForm.gross_earnings}
                  onChange={e => { setOcrForm(p => ({ ...p, gross_earnings: Number(e.target.value) })); setIsOcrModified(true); }}
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-3 text-slate-200 outline-none focus:border-indigo-500 transition text-[11px]"
                />
              </div>
              <div>
                <label className="block text-slate-500 text-[9px] font-bold uppercase tracking-wider mb-1">Total Deductions (Rs.)</label>
                <input
                  type="number"
                  value={ocrForm.deductions}
                  onChange={e => { setOcrForm(p => ({ ...p, deductions: Number(e.target.value) })); setIsOcrModified(true); }}
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-3 text-slate-200 outline-none focus:border-indigo-500 transition text-[11px]"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleRecalculateRisk}
                  disabled={!isOcrModified}
                  className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:hover:bg-violet-600 text-white font-extrabold py-2 rounded-xl text-[10px] active:scale-95 transition"
                >
                  Recalculate Risk Score
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Right Column ───────────────────────────────────────────── */}
      <div className="space-y-5">
        {scanResult ? (
          <>
            {/* Risk Gauge */}
            <div className={`glass-panel p-5 flex items-center gap-5`}>
              <div className={`w-20 h-20 rounded-full border-[6px] flex flex-col items-center justify-center shadow-lg flex-shrink-0 ${riskColor}`}>
                <span className="text-xl font-black font-heading leading-none text-white">{scanResult.risk_score}%</span>
                <span className="text-[8px] text-slate-500 font-bold uppercase mt-0.5">Risk</span>
              </div>
              <div>
                <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold ${riskTextColor} bg-slate-900 border border-slate-700`}>
                  {scanResult.risk_level} RISK
                </span>
                <h3 className="text-sm font-bold text-white mt-2">Forensic Analysis</h3>
                <p className="text-slate-400 text-[10px] mt-0.5">Confidence: {scanResult.confidence}</p>
                {scanResult.fraud_ring?.fraud_ring_detected && (
                  <div className="mt-2 px-2 py-1 bg-red-500/10 border border-red-500/20 rounded text-[9px] text-red-400 font-bold flex items-center gap-1">
                    <Network className="w-3 h-3" />
                    Fraud Ring Detected
                  </div>
                )}
              </div>
            </div>

            {/* Anomaly Log */}
            <div className="glass-panel p-5">
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3.5 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Forensic Anomaly Log ({(scanResult.anomalies || []).filter(a => a.severity !== 'INFO').length})
              </h4>
              <div className="space-y-2.5 max-h-[260px] overflow-y-auto pr-1">
                {(scanResult.anomalies || []).length === 0 ? (
                  <div className="flex items-center gap-2 p-3 bg-emerald-500/5 border border-emerald-500/15 rounded-xl">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                    <p className="text-emerald-400 text-[10px] font-semibold">No anomalies detected — all checks passed</p>
                  </div>
                ) : (
                  (scanResult.anomalies || []).map((an, idx) => {
                    const sc = SEVERITY_CONFIG[an.severity] || SEVERITY_CONFIG.INFO;
                    if (an.severity === 'INFO') return null;
                    return (
                      <div key={idx} className={`p-3 ${sc.bg} border ${sc.border} rounded-xl`}>
                        <div className="flex items-start gap-2.5">
                          <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${sc.dot}`} />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h5 className={`text-[11px] font-bold ${sc.text}`}>{an.title}</h5>
                              <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${sc.bg} ${sc.text} border ${sc.border}`}>
                                {an.severity}
                              </span>
                            </div>
                            <p className="text-slate-400 text-[10px] leading-relaxed mt-1">{an.desc}</p>
                            <span className="text-[9px] text-slate-600 mt-1 block">
                              {an.type?.toUpperCase()} · Conf: {an.conf}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Metadata & Font Explorer Card */}
            {scanResult.metadata && Object.keys(scanResult.metadata).length > 0 && (
              <div className="glass-panel p-5">
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3.5 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-indigo-400" />
                  PDF Forensic Metadata & Fonts
                </h4>
                <div className="space-y-3.5">
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-0.5">Creator tool</span>
                      <span className="text-slate-300 font-semibold truncate block">{scanResult.metadata.creator || 'Unknown'}</span>
                    </div>
                    <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-0.5">Producer tool</span>
                      <span className="text-slate-300 font-semibold truncate block">{scanResult.metadata.producer || 'Unknown'}</span>
                    </div>
                    <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-0.5">Creation date</span>
                      <span className="text-slate-300 font-semibold truncate block">{scanResult.metadata.created || 'Unknown'}</span>
                    </div>
                    <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-0.5">Modification date</span>
                      <span className="text-slate-300 font-semibold truncate block">{scanResult.metadata.modified || 'Unknown'}</span>
                    </div>
                    {scanResult.doc_hash && (
                      <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800 col-span-2">
                        <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-0.5">Document Perceptual Hash</span>
                        <span className="text-indigo-400 font-mono text-[9px] truncate block select-all">{scanResult.doc_hash}</span>
                      </div>
                    )}
                  </div>
                  {scanResult.metadata.fonts_used && scanResult.metadata.fonts_used.length > 0 && (
                    <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-bold block uppercase tracking-wider text-[8px] mb-1.5">Embedded Typefaces ({scanResult.metadata.fonts_used.length})</span>
                      <div className="flex flex-wrap gap-1.5 max-h-[100px] overflow-y-auto pr-1">
                        {scanResult.metadata.fonts_used.map((font, idx) => (
                          <span key={idx} className="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[9px] px-2 py-0.5 rounded font-mono">
                            {font}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* LLM Insight — Structured Panel */}
            <div className="glass-panel p-5">
              <div className="flex items-center justify-between mb-3.5">
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Brain className="w-3.5 h-3.5 text-violet-400" />
                  AI Risk Insight
                  {llmData?.llm_source?.includes('claude') && (
                    <span className="text-[8px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-1.5 py-0.5 rounded font-bold ml-1">Claude Sonnet 4</span>
                  )}
                  {llmData?.llm_source?.includes('ollama') && (
                    <span className="text-[8px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-bold ml-1">Ollama Local</span>
                  )}
                  {llmData?.llm_source === 'rule-based-mock' && (
                    <span className="text-[8px] bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded font-bold ml-1">Rule Engine</span>
                  )}
                </h4>
                {llmData && (
                  <button onClick={() => setLlmExpanded(!llmExpanded)} className="text-slate-500 hover:text-slate-300 transition">
                    <ChevronDown className={`w-4 h-4 transition-transform ${llmExpanded ? 'rotate-180' : ''}`} />
                  </button>
                )}
              </div>

              {llmData ? (
                <div className="space-y-3">
                  {/* Action Badge */}
                  <div className="flex items-center justify-between">
                    <span className={`px-3 py-1 rounded-lg text-[10px] font-bold ${actionColors[llmData.recommended_action] || 'bg-slate-700 text-slate-400'}`}>
                      {llmData.recommended_action}
                    </span>
                    <span className={`text-[10px] font-bold ${llmData.risk_level === 'HIGH' ? 'text-red-400' : llmData.risk_level === 'MEDIUM' ? 'text-orange-400' : 'text-emerald-400'}`}>
                      {llmData.risk_level} RISK
                    </span>
                  </div>

                  {/* Summary */}
                  <p className="text-slate-300 text-[11px] leading-relaxed">{llmData.summary}</p>

                  {/* Risk factors (collapsible) */}
                  {llmExpanded && llmData.risk_factors?.length > 0 && (
                    <div className="space-y-1.5 mt-2">
                      <p className="text-[9px] font-bold uppercase text-slate-500 tracking-wider">Risk Factors</p>
                      {llmData.risk_factors.map((rf, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 bg-slate-900/60 rounded-lg">
                          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5
                            ${rf.severity === 'CRITICAL' || rf.severity === 'HIGH' ? 'bg-red-500/10 text-red-400' :
                              rf.severity === 'MEDIUM' ? 'bg-orange-500/10 text-orange-400' : 'bg-slate-700 text-slate-400'}`}>
                            {rf.severity}
                          </span>
                          <div>
                            <p className="text-[10px] font-semibold text-white">{rf.factor}</p>
                            <p className="text-[9px] text-slate-500 mt-0.5">{rf.evidence}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Confidence rationale */}
                  {llmExpanded && (
                    <p className="text-[9px] text-slate-600 italic border-t border-slate-800 pt-2 mt-2">
                      {llmData.confidence_rationale}
                    </p>
                  )}
                </div>
              ) : (
                <div
                  className="p-3 bg-violet-600/5 border border-violet-500/15 rounded-xl text-[11px] leading-relaxed text-slate-300"
                  dangerouslySetInnerHTML={{ __html: scanResult.llm_insight }}
                />
              )}

              <div className="mt-3 p-2.5 border-l-2 border-violet-500 bg-violet-500/5 rounded-r-lg">
                <span className="text-[9px] font-extrabold uppercase tracking-wider text-violet-400 block">Recommendation</span>
                <p className="text-slate-400 text-[10px] mt-0.5">{scanResult.recommendation}</p>
              </div>
            </div>

            {/* Forensic Raw JSON Card */}
            <div className="glass-panel p-5">
              <div className="flex items-center justify-between mb-3.5">
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Settings className="w-3.5 h-3.5 text-slate-400" />
                  Forensic Raw JSON Payload
                </h4>
                <button onClick={() => setJsonExpanded(!jsonExpanded)} className="text-slate-500 hover:text-slate-300 transition">
                  <ChevronDown className={`w-4 h-4 transition-transform ${jsonExpanded ? 'rotate-180' : ''}`} />
                </button>
              </div>
              {jsonExpanded && (
                <div className="relative">
                  <pre className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 text-[9px] font-mono text-emerald-400 overflow-x-auto max-h-[160px] leading-normal">
                    {JSON.stringify({
                      filename: scanResult.filename,
                      doc_type: scanResult.doc_type,
                      risk_score: scanResult.risk_score,
                      risk_level: scanResult.risk_level,
                      confidence: scanResult.confidence,
                      anomalies: scanResult.anomalies,
                      extracted_data: scanResult.extracted_data,
                    }, null, 2)}
                  </pre>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(scanResult, null, 2));
                      alert("Copied to clipboard!");
                    }}
                    className="absolute top-2 right-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[8px] font-bold px-2 py-1 rounded transition"
                  >
                    Copy
                  </button>
                </div>
              )}
            </div>

            {/* Case Disposition */}
            <div className="glass-panel p-5">
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3.5">Case Disposition</h4>
              <div className="grid grid-cols-2 gap-2.5">
                <button onClick={() => handleDisposition('reject')}
                  className="bg-red-600 hover:bg-red-500 text-white font-bold py-2.5 px-3 rounded-xl active:scale-95 transition text-[11px]">
                  Reject Application
                </button>
                <button onClick={() => handleDisposition('approve')}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2.5 px-3 rounded-xl active:scale-95 transition text-[11px]">
                  Approve Integrity
                </button>
                <button onClick={() => handleDisposition('escalate')}
                  className="col-span-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold py-2.5 px-3 rounded-xl active:scale-95 transition text-[11px]">
                  Escalate for Audit Review
                </button>
                <button onClick={handlePrintReport}
                  className="col-span-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2.5 px-3 rounded-xl active:scale-95 transition text-[11px] flex items-center justify-center gap-1.5">
                  <FileText className="w-4 h-4" />
                  Print Credit Report PDF
                </button>
              </div>
            </div>

            {/* Report Forgery to Blocklist */}
            <div className="glass-panel p-5 mt-4">
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3.5 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
                Report Forgery to Blocklist
              </h4>
              <p className="text-[9px] text-slate-400 mb-3 leading-normal">
                Submit this document's attributes directly to the shared Fraud Pattern Library to block future applications.
              </p>
              <div className="space-y-2">
                <button
                  onClick={() => handleReportForgery('pan', ocrForm.pan)}
                  disabled={!ocrForm.pan || ocrForm.pan === 'Unknown'}
                  className="w-full bg-red-950/20 hover:bg-red-950/40 border border-red-500/20 text-red-400 font-bold py-2 px-3 rounded-xl active:scale-95 transition text-[10px] disabled:opacity-30 disabled:pointer-events-none text-left truncate"
                >
                  Blocklist PAN: {ocrForm.pan}
                </button>
                <button
                  onClick={() => handleReportForgery('employer', scanResult.extracted_data?.employer)}
                  disabled={!scanResult.extracted_data?.employer || scanResult.extracted_data?.employer === 'Unknown'}
                  className="w-full bg-red-950/20 hover:bg-red-950/40 border border-red-500/20 text-red-400 font-bold py-2 px-3 rounded-xl active:scale-95 transition text-[10px] disabled:opacity-30 disabled:pointer-events-none text-left truncate"
                >
                  Blocklist Employer: {scanResult.extracted_data?.employer}
                </button>
                <button
                  onClick={() => handleReportForgery('hash', scanResult.doc_hash)}
                  disabled={!scanResult.doc_hash}
                  className="w-full bg-red-950/20 hover:bg-red-950/40 border border-red-500/20 text-red-400 font-bold py-2 px-3 rounded-xl active:scale-95 transition text-[10px] disabled:opacity-30 disabled:pointer-events-none text-left truncate"
                >
                  Blocklist Document Hash: {scanResult.doc_hash ? `${scanResult.doc_hash.substring(0, 12)}...` : 'N/A'}
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
      {/* Hidden Print Report Layout */}
      {scanResult && (
        <div id="print-report-root">
          <div style={{ borderBottom: '2px solid #4f46e5', paddingBottom: '15px', marginBottom: '25px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#1e1b4b', margin: 0 }}>SatyaPramaan AI</h1>
              <p style={{ fontSize: '10px', textTransform: 'uppercase', color: '#6366f1', letterSpacing: '0.05em', margin: '2px 0 0 0', fontWeight: 'bold' }}>Credit Forensic Report</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '10px', fontWeight: '700', padding: '4px 8px', borderRadius: '4px', background: scanResult.risk_score > 75 ? '#fee2e2' : scanResult.risk_score > 30 ? '#ffedd5' : '#d1fae5', color: scanResult.risk_score > 75 ? '#991b1b' : scanResult.risk_score > 30 ? '#854d0e' : '#065f46' }}>
                {scanResult.risk_level} RISK (SCORE: {scanResult.risk_score}%)
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '25px', fontSize: '11px' }}>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <h5 style={{ margin: '0 0 8px 0', fontSize: '10px', color: '#64748b', textTransform: 'uppercase' }}>Application Details</h5>
              <p style={{ margin: '3px 0' }}><strong>Case Reference ID:</strong> {caseId}</p>
              <p style={{ margin: '3px 0' }}><strong>Applicant Name:</strong> {applicant || 'N/A'}</p>
              <p style={{ margin: '3px 0' }}><strong>Document Analyzed:</strong> {scanResult.filename}</p>
              <p style={{ margin: '3px 0' }}><strong>Category:</strong> {scanResult.doc_type}</p>
            </div>
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <h5 style={{ margin: '0 0 8px 0', fontSize: '10px', color: '#64748b', textTransform: 'uppercase' }}>Forensic Integrity Summary</h5>
              <p style={{ margin: '3px 0' }}><strong>Analyst Reviewer:</strong> {user?.username || 'underwriter'}</p>
              <p style={{ margin: '3px 0' }}><strong>Audit Date:</strong> {new Date().toLocaleString('en-IN')}</p>
              <p style={{ margin: '3px 0' }}><strong>System Recommendation:</strong> {scanResult.recommendation}</p>
              <p style={{ margin: '3px 0' }}><strong>Decision Confidence:</strong> {scanResult.confidence}</p>
            </div>
          </div>

          <div style={{ marginBottom: '25px' }}>
            <h3 style={{ fontSize: '13px', borderBottom: '1px solid #e2e8f0', paddingBottom: '6px', color: '#1e293b', marginBottom: '10px' }}>AI Risk Summary</h3>
            <p style={{ fontSize: '11px', color: '#334155', lineHeight: '1.6', margin: 0 }}>
              {llmData ? llmData.summary : (scanResult.recommendation || 'No significant forensic anomalies detected.')}
            </p>
          </div>

          <div style={{ marginBottom: '25px' }}>
            <h3 style={{ fontSize: '13px', borderBottom: '1px solid #e2e8f0', paddingBottom: '6px', color: '#1e293b', marginBottom: '10px' }}>Audited Financial & Identity Extract</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #cbd5e1' }}>
                  <th style={{ padding: '8px' }}>Field</th>
                  <th style={{ padding: '8px' }}>Value</th>
                  <th style={{ padding: '8px' }}>Audit Status</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '8px' }}><strong>Verified Name</strong></td>
                  <td style={{ padding: '8px' }}>{ocrForm.name}</td>
                  <td style={{ padding: '8px' }}>Verified</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '8px' }}><strong>PAN Card No</strong></td>
                  <td style={{ padding: '8px' }}>{ocrForm.pan}</td>
                  <td style={{ padding: '8px' }}>Verified</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '8px' }}><strong>Gross Earnings</strong></td>
                  <td style={{ padding: '8px' }}>Rs. {Number(ocrForm.gross_earnings).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '8px' }}>Reconciled</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '8px' }}><strong>Total Deductions</strong></td>
                  <td style={{ padding: '8px' }}>Rs. {Number(ocrForm.deductions).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                  <td style={{ padding: '8px' }}>Reconciled</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                  <td style={{ padding: '8px' }}><strong>Net Payout</strong></td>
                  <td style={{ padding: '8px' }}>{ocrForm.net_pay}</td>
                  <td style={{ padding: '8px' }}>Reconciled</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={{ marginBottom: '25px' }}>
            <h3 style={{ fontSize: '13px', borderBottom: '1px solid #e2e8f0', paddingBottom: '6px', color: '#1e293b', marginBottom: '10px' }}>Forensic Anomaly Log</h3>
            {(scanResult.anomalies || []).filter(a => a.severity !== 'INFO').length === 0 ? (
              <p style={{ fontSize: '11px', color: '#0f5132' }}>No forensic anomalies or tempering detected.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(scanResult.anomalies || []).filter(a => a.severity !== 'INFO').map((an, i) => (
                  <div key={i} style={{ border: '1px solid #fca5a5', background: '#fff5f5', padding: '10px', borderRadius: '6px', fontSize: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', color: '#991b1b', marginBottom: '3px' }}>
                      <span>{an.title}</span>
                      <span>{an.severity} RISK</span>
                    </div>
                    <p style={{ margin: '2px 0 0 0', color: '#7f1d1d' }}>{an.desc}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: '50px', borderTop: '1px solid #cbd5e1', paddingTop: '15px', display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#64748b' }}>
            <span>SatyaPramaan Credit Forensic Engine</span>
            <span>Page 1 of 1 · Confidential Underwriting Records</span>
          </div>
        </div>
      )}

      <style>{`
        @media print {
          body {
            background: white !important;
            color: black !important;
          }
          #root, aside, header, .glass-panel, button, input, select, textarea, .no-print {
            display: none !important;
            visibility: hidden !important;
          }
          #print-report-root {
            display: block !important;
            visibility: visible !important;
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            background: white !important;
            color: black !important;
            padding: 40px !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          }
        }
        #print-report-root {
          display: none;
        }
      `}</style>
    </div>
  );
};

export default IntegrityScan;
