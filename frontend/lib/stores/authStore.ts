import { create } from 'zustand';

interface AuthState {
    isAuthenticated: boolean;
    user: string | null;
    jwt: string | null;
    setSession: (jwt: string | null, user: string | null) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: false,
    user: null,
    jwt: null,
    setSession: (jwt: string | null, user: string | null) => {
        set({ isAuthenticated: !!jwt, user, jwt });
    },
    logout: () => {
        set({ isAuthenticated: false, user: null, jwt: null });
    },
}));
