import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { StartupSequence } from "./components/StartupSequence";

import Dashboard from "./pages/Dashboard";
import LiveMonitoring from "./pages/LiveMonitoring";
import Esp32Camera from "./pages/Esp32Camera";
import VideoAnalysis from "./pages/VideoAnalysis";
import HardwareSecurity from "./pages/HardwareSecurity";
import RfidAccess from "./pages/RfidAccess";
import Blockchain from "./pages/Blockchain";
import MerkleTree from "./pages/MerkleTree";
import PrivacyLayer from "./pages/PrivacyLayer";
import Vpap from "./pages/Vpap";
import Ipfs from "./pages/Ipfs";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";

export default function App() {
  const [booted, setBooted] = useState(false);

  return (
    <>
      {!booted && <StartupSequence onDone={() => setBooted(true)} />}
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<LiveMonitoring />} />
          <Route path="/esp32" element={<Esp32Camera />} />
          <Route path="/video" element={<VideoAnalysis />} />
          <Route path="/hardware" element={<HardwareSecurity />} />
          <Route path="/rfid" element={<RfidAccess />} />
          <Route path="/blockchain" element={<Blockchain />} />
          <Route path="/merkle" element={<MerkleTree />} />
          <Route path="/privacy" element={<PrivacyLayer />} />
          <Route path="/vpap" element={<Vpap />} />
          <Route path="/ipfs" element={<Ipfs />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </>
  );
}
