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
        <div className="flex flex-col h-full border border-border rounded-md overflow-hidden">
            <div className="p-3 border-b border-border flex justify-between items-center">
                <h3 className="text-sm font-medium text-foreground font-mono">Strategy Editor</h3>
                <button
                    onClick={handleValidateAndSave}
                    disabled={isSaving}
                    className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50 min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                    {isSaving ? 'Validating...' : 'Compile & Save'}
                </button>
            </div>

            <div className="relative flex-1">
                <textarea
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    className="w-full h-full p-4 bg-background text-foreground/80 font-mono tabular-nums text-sm resize-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary border-none"
                    spellCheck="false"
                />
            </div>

            {error && (
                <div className="p-3 border-t border-destructive/30">
                    <p className="text-sm text-red-500 font-mono break-words">{error}</p>
                </div>
            )}
        </div>
    );
};
