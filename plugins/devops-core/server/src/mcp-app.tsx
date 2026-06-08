import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useApp } from "@modelcontextprotocol/ext-apps/react";
import {
  applyDocumentTheme,
  applyHostStyleVariables,
  applyHostFonts,
} from "@modelcontextprotocol/ext-apps";
import "./styles.css";
import { SetupView } from "./views/Setup";
import { InventoryView } from "./views/Inventory";
import { PlanView } from "./views/Plan";
import { SummaryView } from "./views/Summary";
import type { ViewInput } from "./types";

function EKSApp() {
  const { app, toolInput, hostContext } = useApp({
    name: "EKS Updater",
    version: "1.0.0",
  });

  useEffect(() => {
    if (!hostContext) return;
    if (hostContext.theme) applyDocumentTheme(hostContext.theme);
    if (hostContext.styles?.variables) applyHostStyleVariables(hostContext.styles.variables);
    if (hostContext.styles?.css?.fonts) applyHostFonts(hostContext.styles.css.fonts);
    if (hostContext.safeAreaInsets) {
      const { top, right, bottom, left } = hostContext.safeAreaInsets;
      document.body.style.padding = `${top}px ${right}px ${bottom}px ${left}px`;
    }
  }, [hostContext]);

  if (!toolInput) {
    return (
      <div className="placeholder">
        <svg
          width="44"
          height="44"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
          <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
        </svg>
        <p>Waiting for EKS Updater…</p>
      </div>
    );
  }

  const data = toolInput.structuredContent as ViewInput;

  if (!data?.action) {
    return (
      <div className="placeholder">
        <p>No view data received.</p>
      </div>
    );
  }

  switch (data.action) {
    case "setup":
      return <SetupView data={data} app={app} />;
    case "inventory":
      return <InventoryView data={data} />;
    case "plan":
      return <PlanView data={data} app={app} />;
    case "summary":
      return <SummaryView data={data} />;
    default:
      return (
        <div className="placeholder">
          <p>Unknown view.</p>
        </div>
      );
  }
}

const container = document.getElementById("root");
if (container) {
  const root = createRoot(container);
  root.render(<EKSApp />);
}
