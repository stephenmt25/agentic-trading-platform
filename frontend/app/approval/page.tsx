"use client";

import React, { useCallback } from 'react';
import { CheckCircle2, XCircle, Clock, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';
import { useHITLStore, type HITLRequest } from '@/lib/stores/hitlStore';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function respondToHITL(eventId: string, status: 'APPROVED' | 'REJECTED', reason?: string) {
    const res = await fetch(`${API_BASE_URL}/api/hitl/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: eventId, status, reason }),
    });
    if (!res.ok) throw new Error('Failed to submit HITL response');
}

function AgentScoreBadge({ name, data }: { name: string; data: { score: number; confidence?: number } }) {
    const score = data.score;
    const color = score > 0.3 ? 'text-green-400' : score < -0.3 ? 'text-red-400' : 'text-zinc-400';
    return (
        <div className="flex items-center gap-2 rounded-md bg-zinc-800/50 px-3 py-1.5">
            <span className="text-xs text-zinc-500 uppercase">{name}</span>
            <span className={`text-sm font-mono font-semibold ${color}`}>
                {score >= 0 ? '+' : ''}{score.toFixed(2)}
            </span>
            {data.confidence !== undefined && (
                <span className="text-xs text-zinc-600">({(data.confidence * 100).toFixed(0)}%)</span>
            )}
        </div>
    );
}

function RequestCard({ request }: { request: HITLRequest }) {
    const { updateStatus, removeRequest } = useHITLStore();
    const isPending = request.status === 'PENDING';

    const handleApprove = useCallback(async () => {
        try {
            await respondToHITL(request.event_id, 'APPROVED');
            updateStatus(request.event_id, 'APPROVED');
            setTimeout(() => removeRequest(request.event_id), 3000);
        } catch (e) {
            console.error('Approve failed', e);
        }
    }, [request.event_id, updateStatus, removeRequest]);

    const handleReject = useCallback(async () => {
        try {
            await respondToHITL(request.event_id, 'REJECTED', 'Manual rejection');
            updateStatus(request.event_id, 'REJECTED');
            setTimeout(() => removeRequest(request.event_id), 3000);
        } catch (e) {
            console.error('Reject failed', e);
        }
    }, [request.event_id, updateStatus, removeRequest]);

    const isBuy = request.side === 'BUY';
    const timestamp = new Date(request.timestamp_us / 1000).toLocaleTimeString();
    const rm = request.risk_metrics;

    return (
        <div className={`rounded-lg border p-5 transition-colors ${
            request.status === 'APPROVED' ? 'border-green-500/30 bg-green-500/5' :
            request.status === 'REJECTED' ? 'border-red-500/30 bg-red-500/5' :
            'border-zinc-700 bg-zinc-900'
        }`}>
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ${
                        isBuy ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                        {isBuy ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                        {request.side}
                    </div>
                    <span className="text-lg font-semibold text-zinc-100">{request.symbol}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <Clock size={12} />
                    {timestamp}
                </div>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="rounded-md bg-zinc-800/60 p-2.5">
                    <div className="text-xs text-zinc-500 mb-0.5">Price</div>
                    <div className="font-mono text-sm text-zinc-200">${Number(request.price).toLocaleString()}</div>
                </div>
                <div className="rounded-md bg-zinc-800/60 p-2.5">
                    <div className="text-xs text-zinc-500 mb-0.5">Quantity</div>
                    <div className="font-mono text-sm text-zinc-200">{Number(request.quantity).toFixed(6)}</div>
                </div>
                <div className="rounded-md bg-zinc-800/60 p-2.5">
                    <div className="text-xs text-zinc-500 mb-0.5">Confidence</div>
                    <div className={`font-mono text-sm ${
                        request.confidence > 0.7 ? 'text-green-400' : request.confidence < 0.5 ? 'text-red-400' : 'text-yellow-400'
                    }`}>{(request.confidence * 100).toFixed(1)}%</div>
                </div>
                <div className="rounded-md bg-zinc-800/60 p-2.5">
                    <div className="text-xs text-zinc-500 mb-0.5">Regime</div>
                    <div className={`text-sm ${
                        rm.regime === 'HIGH_VOLATILITY' ? 'text-red-400' :
                        rm.regime === 'CRISIS' ? 'text-red-500 font-bold' : 'text-zinc-300'
                    }`}>{rm.regime}</div>
                </div>
            </div>

            {/* Trigger reason */}
            <div className="flex items-center gap-2 mb-3 rounded-md bg-yellow-500/5 border border-yellow-500/20 px-3 py-2">
                <AlertTriangle size={14} className="text-yellow-500 shrink-0" />
                <span className="text-sm text-yellow-400">{request.trigger_reason}</span>
            </div>

            {/* Agent scores */}
            {Object.keys(request.agent_scores).length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                    {Object.entries(request.agent_scores).map(([name, data]) => (
                        <AgentScoreBadge key={name} name={name} data={data} />
                    ))}
                </div>
            )}

            {/* Risk metrics bar */}
            <div className="flex gap-4 text-xs text-zinc-500 mb-4">
                <span>Alloc: {(rm.allocation_pct * 100).toFixed(1)}%</span>
                <span>DD: {(rm.drawdown_pct * 100).toFixed(1)}%</span>
                <span>RSI: {rm.rsi?.toFixed(1)}</span>
                <span>ATR: {rm.atr?.toFixed(2)}</span>
            </div>

            {/* Action buttons */}
            {isPending ? (
                <div className="flex gap-3">
                    <button
                        onClick={handleApprove}
                        className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-green-600 hover:bg-green-500 text-white font-semibold py-2.5 transition-colors"
                    >
                        <CheckCircle2 size={16} />
                        Approve
                    </button>
                    <button
                        onClick={handleReject}
                        className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-zinc-700 hover:bg-red-600 text-zinc-200 hover:text-white font-semibold py-2.5 transition-colors"
                    >
                        <XCircle size={16} />
                        Reject
                    </button>
                </div>
            ) : (
                <div className={`text-center py-2 rounded-lg text-sm font-semibold ${
                    request.status === 'APPROVED' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                }`}>
                    {request.status}
                </div>
            )}
        </div>
    );
}

export default function ApprovalPage() {
    const { pendingRequests } = useHITLStore();
    const pending = pendingRequests.filter(r => r.status === 'PENDING');
    const resolved = pendingRequests.filter(r => r.status !== 'PENDING');

    return (
        <div className="max-w-3xl mx-auto p-6">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-zinc-100">Trade Approvals</h1>
                {pending.length > 0 && (
                    <span className="flex items-center gap-1.5 rounded-full bg-yellow-500/10 border border-yellow-500/30 px-3 py-1 text-sm text-yellow-400">
                        <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
                        {pending.length} pending
                    </span>
                )}
            </div>

            {pendingRequests.length === 0 ? (
                <div className="text-center py-20 text-zinc-500">
                    <CheckCircle2 size={48} className="mx-auto mb-4 opacity-30" />
                    <p className="text-lg">No pending approvals</p>
                    <p className="text-sm mt-1">Trades requiring human approval will appear here in real-time.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {pending.map(req => (
                        <RequestCard key={req.event_id} request={req} />
                    ))}
                    {resolved.length > 0 && (
                        <>
                            <div className="text-xs text-zinc-600 uppercase tracking-wider pt-4">Recent decisions</div>
                            {resolved.map(req => (
                                <RequestCard key={req.event_id} request={req} />
                            ))}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
