import { BrowserRouter, Routes, Route } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import LiveRunPage from "./pages/LiveRunPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/runs/:runId/live" element={<LiveRunPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
