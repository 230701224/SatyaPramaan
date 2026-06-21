import React, { useState, useContext } from 'react';
import { AuthProvider, AuthContext } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import IntegrityScan from './pages/IntegrityScan';
import CrossDoc from './pages/CrossDoc';
import AuditVault from './pages/AuditVault';
import { 
  ShieldCheck, LayoutDashboard, FileText, Split, 
  Database, LogOut, Moon, Sun, Activity, Search, Bell, HelpCircle 
} from 'lucide-react';

const AppContent = () => {
  const { isAuthenticated, user, logout, loading } = useContext(AuthContext);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [theme, setTheme] = useState('dark');
  const [searchQuery, setSearchQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    if (nextTheme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#030712] text-slate-400">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-sm font-semibold">Initializing SatyaPramaan Secure Client...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  const handleSelectCase = (caseId) => {
    setSelectedCaseId(caseId);
    setActiveTab('scanner');
  };

  const handleClearCase = () => {
    setSelectedCaseId('');
  };

  return (
    <div className="min-h-screen flex theme-bg-app theme-text-main">
      {/* Sidebar Navigation */}
      <aside className="w-72 theme-bg-sidebar border-r theme-border flex flex-col p-6 flex-shrink-0">
        {/* Sidebar Header */}
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 bg-gradient-to-tr from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center text-white shadow-md shadow-indigo-500/20 relative">
            <ShieldCheck className="w-6 h-6 animate-pulse" />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 theme-border rounded-full"></span>
          </div>
          <div>
            <h1 className="text-md font-black tracking-tight font-heading text-white">
              SatyaPramaan <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-indigo-400">AI</span>
            </h1>
            <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Credit Forensic Engine</p>
          </div>
        </div>

        {/* Sidebar Menus */}
        <nav className="space-y-1.5 flex-grow">
          <button
            onClick={() => { setActiveTab('dashboard'); handleClearCase(); }}
            className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-xs font-bold transition ${activeTab === 'dashboard' ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 shadow-inner' : 'text-slate-400 hover:bg-slate-800/40 hover:text-white'}`}
          >
            <LayoutDashboard className="w-4.5 h-4.5" />
            Dashboard
          </button>
          
          <button
            onClick={() => setActiveTab('scanner')}
            className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-xs font-bold transition ${activeTab === 'scanner' ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 shadow-inner' : 'text-slate-400 hover:bg-slate-800/40 hover:text-white'}`}
          >
            <FileText className="w-4.5 h-4.5" />
            Integrity Scanner
          </button>

          <button
            onClick={() => { setActiveTab('cross-doc'); handleClearCase(); }}
            className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-xs font-bold transition ${activeTab === 'cross-doc' ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 shadow-inner' : 'text-slate-400 hover:bg-slate-800/40 hover:text-white'}`}
          >
            <Split className="w-4.5 h-4.5" />
            Crosscheck Analyzer
          </button>

          <button
            onClick={() => { setActiveTab('vault'); handleClearCase(); }}
            className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-xs font-bold transition ${activeTab === 'vault' ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 shadow-inner' : 'text-slate-400 hover:bg-slate-800/40 hover:text-white'}`}
          >
            <Database className="w-4.5 h-4.5" />
            Compliance Vault
          </button>
        </nav>

        {/* Sidebar Footer */}
        <div className="pt-6 border-t border-slate-800/80">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">FastAPI Pipeline v2.4</span>
            </div>
            <span className="text-[9px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded font-extrabold">{user?.role}</span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl">
            <div className="overflow-hidden pr-2">
              <p className="text-[11px] font-bold text-white truncate">{user?.username}</p>
              <p className="text-[9px] text-slate-500 font-semibold truncate">Active Audit Session</p>
            </div>
            <button
              onClick={logout}
              className="text-slate-500 hover:text-red-400 p-1.5 hover:bg-red-500/5 rounded-lg active:scale-95 transition"
              title="Logout Session"
            >
              <LogOut className="w-4.5 h-4.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Workspace Frame */}
      <div className="flex-grow flex flex-col min-h-screen overflow-y-auto">
        {/* Top Header Bar */}
        <header className="px-8 py-5 theme-header border-b theme-border flex justify-between items-center sticky top-0 z-40 backdrop-blur-md">
          <div>
            <h2 className="text-xl font-bold font-heading theme-text-main">
              {activeTab === 'dashboard' && 'Underwriter Cockpit'}
              {activeTab === 'scanner' && 'Integrity Verification Scanner'}
              {activeTab === 'cross-doc' && 'Cross-Document Consistency Matrix'}
              {activeTab === 'vault' && 'Compliance Records Audits'}
            </h2>
            <p className="theme-text-muted text-xs mt-0.5">
              {activeTab === 'dashboard' && 'Real-time loan portfolios metrics and checks queue'}
              {activeTab === 'scanner' && 'Typography character extraction & ELA pixel checks'}
              {activeTab === 'cross-doc' && 'Reconciliation audits (Salary vs Statement vs ITR)'}
              {activeTab === 'vault' && 'Non-repudiable logs of credit analysis decisions'}
            </p>
          </div>

          <div className="flex items-center gap-4 relative">
            {/* Search Bar (Only on first page / Dashboard) */}
            {activeTab === 'dashboard' && (
              <div className="relative w-64 md:w-80">
                <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search cases or IDs..."
                  className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 pl-10 pr-4 outline-none focus:border-indigo-500 transition text-xs font-semibold"
                />
              </div>
            )}

            {/* Notification Bell */}
            <div className="relative">
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-800/40 rounded-xl transition cursor-pointer relative"
                title="System Notifications"
              >
                <Bell className="w-4.5 h-4.5" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border border-slate-900 animate-pulse"></span>
              </button>
              
              {showNotifications && (
                <div className="absolute right-0 mt-2.5 w-80 glass-panel p-4 z-50 shadow-2xl border theme-border theme-bg-sidebar space-y-3">
                  <div className="flex justify-between items-center border-b theme-border pb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Risk Alerts</span>
                    <button onClick={() => setShowNotifications(false)} className="text-[9px] text-indigo-400 font-bold hover:text-indigo-300">Close</button>
                  </div>
                  <div className="space-y-2.5 max-h-60 overflow-y-auto">
                    {[
                      { id: 1, title: 'Math Mismatch', desc: 'Case SP-29402 gross-to-net pay calculation fails reconciliation.', severity: 'CRITICAL', color: 'text-red-400 bg-red-500/10 border-red-500/20' },
                      { id: 2, title: 'Metadata Mismatch', desc: 'Case SP-40192 PDF headers trace back to Adobe edit tools.', severity: 'WARNING', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
                      { id: 3, title: 'Analysis Complete', desc: 'Case SP-82910 HDFC bank ledger verifies with clean status.', severity: 'INFO', color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' }
                    ].map(n => (
                      <div key={n.id} className="p-2 border border-slate-800 rounded-lg hover:bg-slate-800/20 transition text-[10px]">
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-bold text-white">{n.title}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold border ${n.color}`}>{n.severity}</span>
                        </div>
                        <p className="text-slate-400 leading-normal">{n.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Info / Help Symbol */}
            <button
              onClick={() => setShowHelpModal(true)}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800/40 rounded-xl transition cursor-pointer"
              title="Forensics System Documentation"
            >
              <HelpCircle className="w-4.5 h-4.5" />
            </button>

            {/* Pipeline Status Indicator */}
            <div className="hidden lg:flex items-center gap-2 theme-bg-input border theme-border px-3 py-1.5 rounded-full text-[10px] font-bold theme-text-muted shadow-sm">
              <Activity className="w-3.5 h-3.5 text-indigo-400" />
              <span>Pipeline Active</span>
            </div>

            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center p-2 text-slate-400 hover:text-white hover:bg-slate-800/40 rounded-xl transition cursor-pointer"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {theme === 'dark' ? <Moon className="w-4.5 h-4.5 text-indigo-400" /> : <Sun className="w-4.5 h-4.5 text-amber-500" />}
            </button>

            {/* Divider */}
            <span className="h-5 w-px theme-border bg-slate-800/80"></span>

            {/* Profile Block (Analyst 07 / SUPERUSER) */}
            <div className="flex items-center gap-2.5 pl-1.5">
              <div className="w-8 h-8 rounded-full bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold text-xs">
                A7
              </div>
              <div className="hidden md:block leading-tight">
                <p className="text-[11px] font-bold text-white">Analyst 07</p>
                <p className="text-[9px] text-slate-500 font-semibold uppercase tracking-wider">SUPERUSER</p>
              </div>
            </div>
          </div>
        </header>

        {/* Content Pane */}
        <main className="p-8 flex-grow">
          {activeTab === 'dashboard' && <Dashboard onSelectCase={handleSelectCase} searchQuery={searchQuery} />}
          {activeTab === 'scanner' && (
            <IntegrityScan 
              selectedCaseId={selectedCaseId} 
              onClearCase={handleClearCase} 
            />
          )}
          {activeTab === 'cross-doc' && <CrossDoc />}
          {activeTab === 'vault' && <AuditVault />}
        </main>
      </div>

      {/* Interactive Forensics Help Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg glass-panel p-6 bg-[#0b0f19] border theme-border shadow-2xl relative animate-fadeIn text-white">
            <h3 className="text-md font-bold font-heading text-white mb-3">SatyaPramaan AI Forensics Pipeline</h3>
            <p className="text-slate-400 text-[11px] leading-relaxed mb-4">
              Our automated credit risk cockpit deploys a 5-layer computer vision and data validation check system to verify loan applicant details.
            </p>
            <div className="space-y-3.5 max-h-[360px] overflow-y-auto pr-1">
              {[
                { layer: 'Layer 1: Typography Check', desc: 'Uses pdfplumber to scan coordinate-level fonts mismatch in PDF streams. Flags modified financial figures compiled in a mismatched font.' },
                { layer: 'Layer 2: Error Level Analysis', desc: 'Applies hot-colormap overlays to JPEG/PNG compression residual maps, highlighting digital copy-paste anomalies (such as stamp insertion).' },
                { layer: 'Layer 3: Crosscheck Matrix', desc: 'Parses PAN cards, Tax Receipts, and Statements using regex OCR and Textract. Compares employer names and net payout credits side-by-side.' },
                { layer: 'Layer 4: AI Risk Evaluator', desc: 'Generates structured risk factors, severity assessments, and recommendations using custom LLM evaluation prompts.' },
                { layer: 'Layer 5: Relation Fraud Graph', desc: 'Builds syndicated relation graphs via networkx, identifying shared PANs, applicant records, or employers indicating coordinated fraud rings.' }
              ].map((l, i) => (
                <div key={i} className="p-3 bg-slate-800/30 border border-slate-800 rounded-xl text-[10px]">
                  <h5 className="font-bold text-indigo-400 mb-1">{l.layer}</h5>
                  <p className="text-slate-300 leading-normal">{l.desc}</p>
                </div>
              ))}
            </div>
            <button
              onClick={() => setShowHelpModal(false)}
              className="mt-5 w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2 px-4 rounded-xl text-xs active:scale-95 transition cursor-pointer"
            >
              Close Documentation
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const App = () => (
  <AuthProvider>
    <AppContent />
  </AuthProvider>
);

export default App;
