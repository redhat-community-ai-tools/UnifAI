declare global {
    interface Window {
      umami?: {
        identify: (data: Record<string, any> | null) => void;
        track: (event: string, data?: Record<string, any>) => void;
      };
    }
  }
  
  export {};