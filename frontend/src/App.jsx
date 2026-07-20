// App shell + routing. Each page is code-split via React.lazy and rendered inside a
// Suspense boundary so the initial bundle stays small (lazy loading + code splitting).
// When signed out, only the Auth screen is reachable — the app tabs are gated.

import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import BottomNav from "./components/BottomNav.jsx";
import InstallPrompt from "./components/InstallPrompt.jsx";
import { AppProvider, useApp } from "./context/AppContext.jsx";
import { LoadingState } from "./components/States.jsx";

const Auth = lazy(() => import("./pages/Auth.jsx"));
const GoalInput = lazy(() => import("./pages/GoalInput.jsx"));
const Matches = lazy(() => import("./pages/Matches.jsx"));
const Coach = lazy(() => import("./pages/Coach.jsx"));
const Scanner = lazy(() => import("./pages/Scanner.jsx"));
const Translate = lazy(() => import("./pages/Translate.jsx"));
const Rooms = lazy(() => import("./pages/Rooms.jsx"));
const Messages = lazy(() => import("./pages/Messages.jsx"));
const Challenges = lazy(() => import("./pages/Challenges.jsx"));
const Twin = lazy(() => import("./pages/Twin.jsx"));
const Progress = lazy(() => import("./pages/Progress.jsx"));
const Communities = lazy(() => import("./pages/Communities.jsx"));
const Verify = lazy(() => import("./pages/Verify.jsx"));
const Marketplace = lazy(() => import("./pages/Marketplace.jsx"));
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Lessons = lazy(() => import("./pages/Lessons.jsx"));
const Career = lazy(() => import("./pages/Career.jsx"));

function AuthedApp() {
  return (
    <>
      <Nav />
      <main className="container">
        <Suspense fallback={<LoadingState />}>
          <Routes>
            <Route path="/" element={<GoalInput />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/coach" element={<Coach />} />
            <Route path="/scanner" element={<Scanner />} />
            <Route path="/translate" element={<Translate />} />
            <Route path="/rooms" element={<Rooms />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/challenges" element={<Challenges />} />
            <Route path="/twin" element={<Twin />} />
            <Route path="/progress" element={<Progress />} />
            <Route path="/community" element={<Communities />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/market" element={<Marketplace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/lessons" element={<Lessons />} />
            <Route path="/career" element={<Career initialTab="portfolio" />} />
            {/* Back-compat deep links open the matching Career sub-tab */}
            <Route path="/resume" element={<Career initialTab="resume" />} />
            <Route path="/interview" element={<Career initialTab="interview" />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <BottomNav />
    </>
  );
}

function Shell() {
  const { isAuthed } = useApp();
  return (
    <Suspense fallback={<LoadingState />}>
      {isAuthed ? <AuthedApp /> : <Auth />}
    </Suspense>
  );
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Shell />
        <InstallPrompt />
      </BrowserRouter>
    </AppProvider>
  );
}
