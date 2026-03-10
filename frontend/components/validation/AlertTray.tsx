import React, { useState } from 'react';
import { useAlerts } from '../../lib/hooks/useAlerts';
import { Bell, CheckCircle2, ChevronRight, AlertOctagon } from 'lucide-react';
import { ValidationAlert } from '../../lib/types';

export const AlertTray: React.FC = () => {
    const { alerts, unreadCount, markAsRead } = useAlerts();
    const [isOpen, setIsOpen] = useState(false);

    const toggle = () => setIsOpen(!isOpen);

    return (
        <div className={`fixed right-0 top-0 h-full w-80 bg-slate-900 border-l border-slate-700 shadow-2xl transition-transform duration-300 transform ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>

            {/* Toggle Button */}
            <button
                onClick={toggle}
                className="absolute -left-12 top-20 bg-slate-800 p-2 rounded-l-md border border-r-0 border-slate-700 hover:bg-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
                <div className="relative">
                    <Bell size={20} className="text-slate-300" />
                    {unreadCount > 0 && (
                        <span className="absolute -top-2 -right-2 bg-rose-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full animate-pulse">
                            {unreadCount}
                        </span>
                    )}
                </div>
            </button>

            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm">
                <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
                    Validation Engine
                </h2>
                <button onClick={toggle}>
                    <ChevronRight size={20} className="text-slate-400 hover:text-white" />
                </button>
            </div>

            {/* List */}
            <div className="overflow-y-auto h-[calc(100vh-65px)] p-4 space-y-4 bg-slate-900">
                {alerts.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm">
                        <CheckCircle2 size={32} className="mb-2 text-emerald-500/50" />
                        <p>All safety checks passing.</p>
                    </div>
                ) : (
                    alerts.map((alert: ValidationAlert) => (
                        <div
                            key={alert.event_id}
                            className={`p-4 rounded-lg border flex flex-col gap-2 relative transition-all duration-300 ${alert.verdict === 'RED'
                                    ? 'bg-rose-950/30 border-rose-500/50 text-rose-200'
                                    : 'bg-amber-950/30 border-amber-500/50 text-amber-200'
                                } ${!alert.read ? 'opacity-100' : 'opacity-60 scale-95'}`}
                        >
                            {!alert.read && <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-current animate-ping" />}

                            <div className="flex items-center gap-2 text-sm font-bold tracking-tight">
                                {alert.verdict === 'RED' ? <AlertOctagon size={16} /> : <AlertOctagon size={16} />}
                                <span>{alert.check_type}</span>
                                <span className="ml-auto text-[10px] font-mono opacity-50">{new Date(alert.timestamp_us / 1000).toLocaleTimeString()}</span>
                            </div>

                            <p className="text-xs opacity-90 leading-relaxed font-mono">
                                {alert.reason || 'Anomaly detected during evaluation.'}
                            </p>

                            {/* Action */}
                            {alert.verdict === 'RED' && !alert.read && (
                                <button
                                    onClick={() => markAsRead(alert.event_id)}
                                    className="mt-2 text-xs bg-rose-500 hover:bg-rose-600 text-white font-bold py-1 px-3 rounded shadow"
                                >
                                    ACKNOWLEDGE HALT
                                </button>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
