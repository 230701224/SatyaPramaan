import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Loader2, Database, ShieldAlert, CheckSquare } from 'lucide-react';

const AuditVault = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      const res = await axios.get('/api/audit-logs');
      setLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => 
    log.action.toLowerCase().includes(search.toLowerCase()) ||
    (log.notes && log.notes.toLowerCase().includes(search.toLowerCase())) ||
    log.username.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="glass-panel p-6 animate-fadeIn">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h4 className="text-md font-bold font-heading theme-text-main">Underwriting Compliance Audit Vault</h4>
          <p className="text-slate-400 text-xs mt-0.5">Secure, non-repudiable logs of credit actions and scans</p>
        </div>
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search logs by action or user..."
            className="w-full theme-bg-input border theme-border theme-text-main rounded-xl py-2 px-4 pl-10 outline-none focus:border-indigo-500 transition text-xs font-semibold"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center py-16 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-2" />
          <p className="text-sm font-semibold">Connecting to FastAPI audits ledger...</p>
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Database className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No audit records located in database logs</p>
        </div>
      ) : (
        <div className="overflow-x-auto border border-slate-700/40 rounded-xl">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-900/60 border-b border-slate-700/50 text-slate-400">
                <th className="p-4 font-semibold uppercase">Timestamp</th>
                <th className="p-4 font-semibold uppercase">Actor</th>
                <th className="p-4 font-semibold uppercase">Action Token</th>
                <th className="p-4 font-semibold uppercase">Security Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredLogs.map((log) => {
                const isDecision = log.action.includes('DISPOSITION');
                const isLogin = log.action.includes('LOGIN');

                return (
                  <tr key={log.id} className="hover:bg-slate-800/20 transition">
                    <td className="p-4 text-slate-400 font-medium">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="p-4 font-bold text-white">
                      {log.username}
                    </td>
                    <td className="p-4">
                      <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold flex items-center gap-1 w-fit ${isDecision ? 'bg-red-500/10 text-red-400 border border-red-500/20' : isLogin ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-800 text-slate-400'}`}>
                        {isDecision ? <ShieldAlert className="w-3 h-3" /> : <CheckSquare className="w-3 h-3" />}
                        {log.action}
                      </span>
                    </td>
                    <td className="p-4 text-slate-300 max-w-sm truncate" title={log.notes}>
                      {log.notes}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AuditVault;
