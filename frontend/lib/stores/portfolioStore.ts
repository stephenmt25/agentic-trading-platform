import { create } from 'zustand';
import { PnLSnapshot, Profile, Order } from '../types';

interface PortfolioState {
    profiles: Profile[];
    activeProfileId: string | null;
    pnlData: Record<string, PnLSnapshot>;
    setProfiles: (profiles: Profile[]) => void;
    setActiveProfileId: (id: string | null) => void;
    updatePnlData: (profileId: string, snapshot: PnLSnapshot) => void;
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
    profiles: [],
    activeProfileId: null,
    pnlData: {},
    setProfiles: (profiles) => set({ profiles }),
    setActiveProfileId: (id) => set({ activeProfileId: id }),
    updatePnlData: (profileId, snapshot) => set((state) => ({
        pnlData: { ...state.pnlData, [profileId]: snapshot }
    }))
}));
