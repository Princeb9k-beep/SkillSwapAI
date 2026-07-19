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
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Lessons = lazy(() => import("./pages/Lessons.jsx"));
const ResumeBuilder = lazy(() => import("./pages/ResumeBuilder.jsx"));
const InterviewSimulator = lazy(() => import("./pages/InterviewSimulator.jsx"));

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
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/lessons" element={<Lessons />} />
            <Route path="/resume" element={<ResumeBuilder />} />
            <Route path="/interview" element={<InterviewSimulator />} />
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
