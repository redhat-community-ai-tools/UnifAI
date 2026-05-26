import React, { createContext, useContext, useState, useCallback } from 'react';

export type SharedPanelView = 'list' | 'send-choice' | 'send-user' | 'send-team';

export interface ShareItem {
  itemKind: 'resource' | 'blueprint';
  itemId: string;
  itemName?: string;
}

export interface SharedContextType {
  isSharedPanelOpen: boolean;
  sharedPanelView: SharedPanelView;
  shareItem: ShareItem | null;

  openSharedPanel: (view?: SharedPanelView) => void;
  closeSharedPanel: () => void;
  setSharedPanelView: (view: SharedPanelView) => void;
  setShareItem: (item: ShareItem | null) => void;
  openShareForItem: (item: ShareItem) => void;
}

const SharedContext = createContext<SharedContextType | undefined>(undefined);

export function SharedProvider({ children }: { children: React.ReactNode }) {
  const [isSharedPanelOpen, setIsSharedPanelOpen] = useState(false);
  const [sharedPanelView, setSharedPanelView] = useState<SharedPanelView>('list');
  const [shareItem, setShareItem] = useState<ShareItem | null>(null);

  const openSharedPanel = useCallback((view: SharedPanelView = 'list') => {
    setSharedPanelView(view);
    setIsSharedPanelOpen(true);
  }, []);

  const closeSharedPanel = useCallback(() => {
    setIsSharedPanelOpen(false);
    setShareItem(null);
  }, []);

  const openShareForItem = useCallback((item: ShareItem) => {
    setShareItem(item);
    setSharedPanelView('send-choice');
    setIsSharedPanelOpen(true);
  }, []);

  const value: SharedContextType = {
    isSharedPanelOpen,
    sharedPanelView,
    shareItem,
    openSharedPanel,
    closeSharedPanel,
    setSharedPanelView,
    setShareItem,
    openShareForItem,
  };

  return (
    <SharedContext.Provider value={value}>
      {children}
    </SharedContext.Provider>
  );
}

export function useShared() {
  const context = useContext(SharedContext);
  if (context === undefined) {
    throw new Error('useShared must be used within a SharedProvider');
  }
  return context;
}
