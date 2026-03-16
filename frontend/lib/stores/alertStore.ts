import { create } from 'zustand';
import { ValidationAlert } from '../types';

interface AlertState {
    alerts: ValidationAlert[];
    unreadCount: number;
    addAlert: (alert: ValidationAlert) => void;
    markAsRead: (eventId: string) => void;
    clearAll: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
    alerts: [],
    unreadCount: 0,
    addAlert: (alert) => set((state) => {
        // keeping latest 50 for memory
        const newAlerts = [{ ...alert, read: false }, ...state.alerts].slice(0, 50);
        return { alerts: newAlerts, unreadCount: state.unreadCount + 1 };
    }),
    markAsRead: (eventId) => set((state) => ({
        alerts: state.alerts.map(a => a.event_id === eventId ? { ...a, read: true } : a),
        unreadCount: Math.max(0, state.unreadCount - 1)
    })),
    clearAll: () => set({ alerts: [], unreadCount: 0 })
}));
