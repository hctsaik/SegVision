import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { createCimShellHost, createE2EHost } from "./host";
import { useViewStore } from "./store";
import "./styles.css";

const params = new URLSearchParams(window.location.search);
const sidecar = params.get("sidecar") || "";
const hostWindow = window as unknown as {
  __SEGVISION_E2E_HOST__?: unknown;
  __SEGVISION_CIM_HOST__?: unknown;
  __SEGVISION_NATIVEAPP__?: { sidecarUrl?: string; secret?: string };
  __SEGVISION_E2E__?: {
    setViewport: (viewport: { zoom: number; panX: number; panY: number; dpr: number }) => void;
    getViewport: () => { zoom: number; panX: number; panY: number; dpr: number };
    getViewSize: () => { width: number; height: number };
  };
};

if (import.meta.env.DEV && params.get("e2e") === "1") {
  const dataset = params.get("dataset") || "";
  const output = params.get("output") || "";
  const secret = params.get("secret") || "";
  hostWindow.__SEGVISION_E2E_HOST__ = createE2EHost(sidecar, secret, dataset, output);
  hostWindow.__SEGVISION_E2E__ = {
    setViewport: (viewport) => useViewStore.getState().setViewport(viewport),
    getViewport: () => useViewStore.getState().viewport,
    getViewSize: () => useViewStore.getState().viewSize,
  };
} else if (
  params.get("host") === "cim" &&
  hostWindow.__SEGVISION_NATIVEAPP__?.sidecarUrl &&
  hostWindow.__SEGVISION_NATIVEAPP__.secret
) {
  hostWindow.__SEGVISION_CIM_HOST__ = createCimShellHost(
    hostWindow.__SEGVISION_NATIVEAPP__.sidecarUrl,
    hostWindow.__SEGVISION_NATIVEAPP__.secret,
  );
} else if (import.meta.env.DEV && params.get("host") === "cim" && sidecar && params.get("secret")) {
  // Keep the standalone development shell working; packaged NativeApp launches use the injected config above.
  hostWindow.__SEGVISION_CIM_HOST__ = createCimShellHost(sidecar, params.get("secret") || "");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
