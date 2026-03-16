'use client';

import React, { useState } from 'react';
import { apiClient } from '../../lib/api/client';

interface RuleEditorProps {
    initialJson?: string;
    onSave?: () => void;
}

export const JSONRuleEditor: React.FC<RuleEditorProps> = ({ initialJson = '{\n  "rules": [\n    \n  ]\n}', onSave }) => {
    const [value, setValue] = useState(initialJson);
    const [error, setError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    const handleValidateAndSave = async () => {
        try {
            setIsSaving(true);
            setError(null);
            // Client validation
            const parsed = JSON.parse(value);

            // Server validation via Strategy Agent Proxy
            const response = await apiClient.post<{ status: string, id: string }>('/profiles/', {
                rules_json: parsed
            });

            console.log('Saved', response);
            if (onSave) onSave();

        } catch (e: any) {
            setError(e.response ? JSON.stringify(e.response.data.errors) : e.message);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-slate-900 border border-slate-700 shadow-xl rounded-xl overflow-hidden">
            <div className="bg-slate-800 p-3 border-b border-slate-700 flex justify-between items-center">
                <h3 className="text-sm font-semibold text-slate-300 font-mono">Strategy Editor</h3>
                <button
                    onClick={handleValidateAndSave}
                    disabled={isSaving}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-1.5 px-4 rounded transition-colors disabled:opacity-50"
                >
                    {isSaving ? 'VALIDATING...' : 'COMPILE & SAVE'}
                </button>
            </div>

            <div className="relative flex-1">
                <textarea
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    className="w-full h-full p-4 bg-[#0d1117] text-slate-300 font-mono text-sm resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500 border-none"
                    spellCheck="false"
                />
            </div>

            {error && (
                <div className="bg-rose-950/50 p-3 border-t border-rose-900/50">
                    <p className="text-xs text-rose-400 font-mono break-words">{error}</p>
                </div>
            )}
        </div>
    );
};
