"use client";

import React, { useState } from 'react';
import { useAlerts } from '../../lib/hooks/useAlerts';
import { Bell, CheckCircle2, ChevronRight, AlertOctagon } from 'lucide-react';
import { ValidationAlert } from '../../lib/types';

export const AlertTray: React.FC = () => {
    const { alerts, unreadCount, markAsRead } = useAlerts();
    const [isOpen, setIsOpen] = useState(false);

    const toggle = () => setIsOpen(!isOpen);

    return (
        <>
            {/* Toggle Button Container for Top Nav */}
            <button
                onClick={toggle}
                className="relative p-2 rounded-md border border-border bg-card hover:bg-accent transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Open validation alerts"
            >
                <Bell size={18} className="text-muted-foreground" />
                {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center bg-red-500 text-white text-xs font-medium rounded-full">
                        {unreadCount}
                    </span>
                )}
            </button>

            <div className={`fixed z-50 right-0 top-0 h-full w-80 bg-card border-l border-border transition-transform duration-200 ease-out transform ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>

            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
                <h2 className="text-base font-medium text-foreground">
                    Validation Engine
                </h2>
                <button onClick={toggle} className="min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" aria-label="Close validation panel">
                    <ChevronRight size={20} className="text-muted-foreground hover:text-foreground" />
                </button>
            </div>

            {/* List */}
            <div className="overflow-y-auto h-[calc(100vh-65px)] p-4 space-y-3">
                {alerts.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm">
                        <CheckCircle2 size={24} className="mb-2 text-emerald-500/50" />
                        <p>All safety checks passing.</p>
                    </div>
                ) : (
                    alerts.map((alert: ValidationAlert) => (
                        <div
                            key={alert.event_id}
                            className={`p-3 rounded-md border flex flex-col gap-2 relative ${alert.verdict === 'RED'
                                    ? 'border-red-500/30 text-red-500'
                                    : 'border-amber-500/30 text-amber-500'
                                } ${!alert.read ? 'opacity-100' : 'opacity-60'}`}
                        >
                            {!alert.read && <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-current" />}

                            <div className="flex items-center gap-2 text-sm font-medium tracking-tight">
                                <AlertOctagon size={16} />
                                <span>{alert.check_type}</span>
                                <span className="ml-auto text-xs font-mono tabular-nums opacity-50">{new Date(alert.timestamp_us / 1000).toLocaleTimeString()}</span>
                            </div>

                            <p className="text-xs opacity-90 leading-relaxed font-mono">
                                {alert.reason || 'Anomaly detected during evaluation.'}
                            </p>

                            {/* Action */}
                            {alert.verdict === 'RED' && !alert.read && (
                                <button
                                    onClick={() => markAsRead(alert.event_id)}
                                    className="mt-1 text-xs bg-red-500 hover:bg-red-600 text-white font-medium py-2 px-3 rounded-md min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                                >
                                    ACKNOWLEDGE HALT
                                </button>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
        </>
    );
};
