import React, { createContext, useState, useContext, useEffect } from "react";

type Theme = "dark" | "light";

interface ThemeColorsContext {
  primaryHex: string;
  setPrimaryHex: (hexColor: string) => void;
}

interface ThemeContextType extends ThemeColorsContext {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Default to dark mode, but check localStorage for saved preference
  const [theme, setTheme] = useState<Theme>(() => {
    const savedTheme = localStorage.getItem("theme");
    return (savedTheme as Theme) || "dark";
  });

  // Primary color stored as hex for persistence
  const [primaryHex, setPrimaryHexState] = useState<string>(() => {
    return localStorage.getItem("primary") || "#A60000";
  });

  // Convert hex to HSL string of the format expected by Tailwind CSS variables: "H S% L%"
  function hexToHslString(hex: string): string {
    const sanitized = hex.replace("#", "");
    const r = parseInt(sanitized.substring(0, 2), 16) / 255;
    const g = parseInt(sanitized.substring(2, 4), 16) / 255;
    const b = parseInt(sanitized.substring(4, 6), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    let s = 0;
    const l = (max + min) / 2;

    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max - min);
      switch (max) {
        case r:
          h = (g - b) / d + (g < b ? 6 : 0);
          break;
        case g:
          h = (b - r) / d + 2;
          break;
        case b:
          h = (r - g) / d + 4;
          break;
      }
      h /= 6;
    }

    const hh = Math.round(h * 360);
    const ss = Math.round(s * 100);
    const ll = Math.round(l * 100);
    return `${hh} ${ss}% ${ll}%`;
  }

  const updatePrimaryCssVariables = (hexColor: string) => {
    const hsl = hexToHslString(hexColor);
    const body = document.body;
    body.style.setProperty("--primary", hsl);
    // Keep foreground white for best contrast in our palette
    body.style.setProperty("--primary-foreground", "0 0% 98%");
  };

  // Update body and html classes when theme changes
  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    
    // Remove old classes
    root.classList.remove("dark", "light");
    body.classList.remove("light-mode", "dark-mode");
    
    // Add new classes - both Tailwind's expected 'dark' class and custom classes for CSS variables
    if (theme === "dark") {
      root.classList.add("dark");
      body.classList.add("dark-mode");
    } else {
      root.classList.add("light");
      body.classList.add("light-mode");
    }
    
    localStorage.setItem("theme", theme);
    // Re-apply primary color on theme change so inline CSS variables win
    updatePrimaryCssVariables(primaryHex);
  }, [theme]);

  // Initialize primary CSS variables on mount and whenever primaryHex changes
  useEffect(() => {
    updatePrimaryCssVariables(primaryHex);
    localStorage.setItem("primary", primaryHex);
  }, [primaryHex]);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const setPrimaryHex = (hexColor: string) => {
    setPrimaryHexState(hexColor);
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, primaryHex, setPrimaryHex }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
