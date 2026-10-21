import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import type { User } from './types';

type SessionContextValue = { user: User | null; booting: boolean; signIn: (email: string, password: string) => Promise<void>; signOut: () => Promise<void>; };
const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: React.PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  useEffect(() => {
    api.hasSession().then((hasSession) => hasSession ? api.me().then(setUser).catch(() => api.logout()) : undefined).finally(() => setBooting(false));
  }, []);
  const value = useMemo(() => ({
    user,
    booting,
    signIn: async (email: string, password: string) => { const result = await api.login(email, password); setUser(result.user || await api.me()); },
    signOut: async () => { await api.logout(); setUser(null); },
  }), [booting, user]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error('useSession must be used inside SessionProvider');
  return context;
}
