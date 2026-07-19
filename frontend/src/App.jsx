// App shell + routing. Each page is code-split via React.lazy and rendered inside a
// Suspense boundary so the initial bundle stays small (lazy loading + code splitting).
// When signed out, only the Auth screen is reachable — the app tabs are gated.

import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import { AppProvider, useApp } from "./context/AppContext.jsx";
import { LoadingState } from "./components/States.jsx";

const Auth = lazy(() => import("./pages/Auth.jsx"));
const GoalInput = lazy(() => import("./pages/GoalInput.jsx"));
const Matches = lazy(() => import("./pages/Matches.jsx"));
const Progress = lazy(() => import("./pages/Progress.jsx"));
const Communities = lazy(() => import("./pages/Communities.jsx"));
const Verify = lazy(() => import("./pages/Verify.jsx"));
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
            <Route path="/progress" element={<Progress />} />
            <Route path="/community" element={<Communities />} />
            <Route path="/verify" element={<Verify />} />
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
      </BrowserRouter>
    </AppProvider>
  );
}
