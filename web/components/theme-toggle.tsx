"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const current = document.documentElement.classList.contains("light") ? "light" : "dark";
    setTheme(current);
  }, []);

  function applyTheme(nextTheme: Theme) {
    document.documentElement.classList.toggle("light", nextTheme === "light");
    localStorage.setItem("llmh-theme", nextTheme);
    setTheme(nextTheme);
  }

  return (
    <button
      className="ghost-button theme-button mono"
      type="button"
      onClick={() => applyTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? "light view" : "dark view"}
    </button>
  );
}
