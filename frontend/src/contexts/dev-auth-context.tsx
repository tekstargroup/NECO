"use client";

import { createContext, useContext, ReactNode } from "react";

export interface DevAuthContextValue {
  isDevAuth: boolean;
  orgId: string | null;
}

const DevAuthContext = createContext<DevAuthContextValue>({
  isDevAuth: false,
  orgId: null,
});

export function DevAuthProvider({
  children,
  isDevAuth,
  orgId,
}: {
  children: ReactNode;
  isDevAuth: boolean;
  orgId: string | null;
}) {
  return (
    <DevAuthContext.Provider value={{ isDevAuth, orgId }}>
      {children}
    </DevAuthContext.Provider>
  );
}

export function useDevAuthContext() {
  return useContext(DevAuthContext);
}
