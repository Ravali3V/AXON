import { Link, Route, Routes } from "react-router-dom";
import { Input } from "./pages/Input";
import { Progress } from "./pages/Progress";
import { Report } from "./pages/Report";
import { Methodology } from "./pages/Methodology";
import { Override } from "./pages/Override";

export function App() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <Link to="/" style={{ fontWeight: 700 }}>
          AXON
        </Link>
        <Link to="/methodology">Methodology</Link>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Input />} />
          <Route path="/audits/:id" element={<Progress />} />
          <Route path="/audits/:id/report" element={<Report />} />
          <Route path="/audits/:id/override" element={<Override />} />
          <Route path="/methodology" element={<Methodology />} />
        </Routes>
      </main>
    </div>
  );
}
