// App shell + routing. Each page is code-split via React.lazy and rendered inside a
// Suspense boundary so the initial bundle stays small (lazy loading + code splitting).

import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import { AppProvider } from "./context/AppContext.jsx";
import { LoadingState } from "./components/States.jsx";

const GoalInput = lazy(() => import("./pages/GoalInput.jsx"));
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Lessons = lazy(() => import("./pages/Lessons.jsx"));
const ResumeBuilder = lazy(() => import("./pages/ResumeBuilder.jsx"));
const InterviewSimulator = lazy(() => import("./pages/InterviewSimulator.jsx"));

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Nav />
        <main className="container">
          <Suspense fallback={<LoadingState />}>
            <Routes>
              <Route path="/" element={<GoalInput />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/lessons" element={<Lessons />} />
              <Route path="/resume" element={<ResumeBuilder />} />
              <Route path="/interview" element={<InterviewSimulator />} />
            </Routes>
          </Suspense>
        </main>
      </BrowserRouter>
    </AppProvider>
  );
}
