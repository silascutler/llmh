export function ThemeScript() {
  const code = `
    (() => {
      try {
        const stored = localStorage.getItem("llmh-theme");
        const theme = stored === "light" ? "light" : "dark";
        document.documentElement.classList.toggle("light", theme === "light");
      } catch (_) {}
    })();
  `;

  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
