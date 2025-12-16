import React, { createContext, useState, useContext, useEffect } from "react";
import { hexToHsl } from "@/lib/colorUtils";

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
  // Uses shared colorUtils to avoid code duplication
  function hexToHslString(hex: string): string {
    const hsl = hexToHsl(hex);
    return `${hsl.h} ${hsl.s}% ${hsl.l}%`;
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
