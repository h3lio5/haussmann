import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Evals } from "./Evals";
import "./styles.css";

function Root() {
  const [place, setPlace] = useState(window.location.hash);
  useEffect(() => {
    const moved = () => setPlace(window.location.hash);
    window.addEventListener("hashchange", moved);
    return () => window.removeEventListener("hashchange", moved);
  }, []);
  return place === "#evals" ? <Evals /> : <App />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
