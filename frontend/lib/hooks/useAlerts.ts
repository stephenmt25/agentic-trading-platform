"use client";

import { useEffect } from 'react';
import { useAlertStore } from '../stores/alertStore';
import { wsClient } from '../ws/client';

export function useAlerts() {
    const { alerts, unreadCount, markAsRead, clearAll } = useAlertStore();

    useEffect(() => {
        wsClient.connect();
    }, []);

    return { alerts, unreadCount, markAsRead, clearAll };
}
