// App shell + routing. Each page is code-split via React.lazy and rendered inside a
// Suspense boundary so the initial bundle stays small (lazy loading + code splitting).
// When signed out, only the Auth screen is reachable — the app tabs are gated.

import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Route, Routes, Navigate, Link } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import BottomNav from "./components/BottomNav.jsx";
import ActionDock from "./components/ActionDock.jsx";
import RequirePlan from "./components/RequirePlan.jsx";
import InstallPrompt from "./components/InstallPrompt.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import { AppProvider, useApp } from "./context/AppContext.jsx";
import { LoadingState } from "./components/States.jsx";
import { SkeletonPage } from "./components/Skeleton.jsx";

const Auth = lazy(() => import("./pages/Auth.jsx"));
const Landing = lazy(() => import("./pages/Landing.jsx"));
const GoalInput = lazy(() => import("./pages/GoalInput.jsx"));
const AiHub = lazy(() => import("./pages/AiHub.jsx"));
const Stream = lazy(() => import("./pages/Stream.jsx"));
const Discover = lazy(() => import("./pages/Discover.jsx"));
const LearnHub = lazy(() => import("./pages/LearnHub.jsx"));
const ConnectHub = lazy(() => import("./pages/ConnectHub.jsx"));
const GrowHub = lazy(() => import("./pages/GrowHub.jsx"));
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
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Meetups = lazy(() => import("./pages/Meetups.jsx"));
const Partners = lazy(() => import("./pages/Partners.jsx"));
const Admin = lazy(() => import("./pages/Admin.jsx"));
const Academy = lazy(() => import("./pages/Academy.jsx"));
const Plans = lazy(() => import("./pages/Plans.jsx"));
const Onboarding = lazy(() => import("./pages/Onboarding.jsx"));
const Search = lazy(() => import("./pages/Search.jsx"));
const Flashcards = lazy(() => import("./pages/Flashcards.jsx"));
const Sessions = lazy(() => import("./pages/Sessions.jsx"));
const Feed = lazy(() => import("./pages/Feed.jsx"));
const Buddies = lazy(() => import("./pages/Buddies.jsx"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail.jsx"));
const Profile = lazy(() => import("./pages/Profile.jsx"));
const OAuthCallback = lazy(() => import("./pages/OAuthCallback.jsx"));
const VerifyCertificate = lazy(() => import("./pages/VerifyCertificate.jsx"));
const Privacy = lazy(() => import("./pages/Legal.jsx").then((m) => ({ default: m.Privacy })));
const Terms = lazy(() => import("./pages/Legal.jsx").then((m) => ({ default: m.Terms })));

function AuthedApp() {
  const { user } = useApp();
  const [dockOpen, setDockOpen] = useState(false);
  // First-run: guide brand-new users before dropping them into the full app.
  if (user && user.onboarded === false) {
    return (
      <Suspense fallback={<LoadingState />}>
        <Onboarding />
      </Suspense>
    );
  }
  return (
    <>
      <Nav onCreate={() => setDockOpen(true)} />
      {user && user.email_verified === false && (
        <div className="verify-banner">
          <span>Verify your email to secure your account.</span>
          <Link to="/settings">Verify now</Link>
        </div>
      )}
      <main className="container">
        {/* Skeleton (not a spinner) while a tab's lazy chunk loads — reserves
            layout and reads as faster when switching tabs. */}
        <Suspense fallback={<SkeletonPage label="Loading page…" />}>
          <Routes>
            {/* Five-section nav: AI Hub (home) + Learn / Connect / Grow hubs. */}
            <Route path="/" element={<AiHub />} />
            <Route path="/learn" element={<LearnHub />} />
            <Route path="/connect" element={<ConnectHub />} />
            <Route path="/grow" element={<GrowHub />} />
            <Route path="/goal" element={<GoalInput />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/coach" element={<Coach />} />
            <Route path="/scanner" element={<Scanner />} />
            <Route path="/translate" element={<Translate />} />
            <Route path="/rooms" element={<Rooms />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/meetups" element={<Meetups />} />
            <Route path="/partners" element={<Partners />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/academy" element={<Academy />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/challenges" element={<Challenges />} />
            <Route path="/twin" element={<RequirePlan need="pro" name="AI Twin"><Twin /></RequirePlan>} />
            <Route path="/progress" element={<Progress />} />
            <Route path="/search" element={<Search />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/feed" element={<Feed />} />
            <Route path="/buddies" element={<Buddies />} />
            <Route path="/u/:id" element={<Profile />} />
            <Route path="/community" element={<Communities />} />
            <Route path="/verify" element={<RequirePlan need="elite" name="Skill verification"><Verify /></RequirePlan>} />
            <Route path="/market" element={<Marketplace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/lessons" element={<Lessons />} />
            <Route path="/stream" element={<Stream />} />
            <Route path="/discover" element={<Discover />} />
            <Route path="/flashcards" element={<Flashcards />} />
            <Route path="/career" element={<RequirePlan need="pro" name="Career tools"><Career initialTab="portfolio" /></RequirePlan>} />
            {/* Back-compat deep links open the matching Career sub-tab */}
            <Route path="/resume" element={<RequirePlan need="pro" name="Career tools"><Career initialTab="resume" /></RequirePlan>} />
            <Route path="/interview" element={<RequirePlan need="pro" name="Career tools"><Career initialTab="interview" /></RequirePlan>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <BottomNav onCreate={() => setDockOpen(true)} />
      <ActionDock open={dockOpen} onClose={() => setDockOpen(false)} />
    </>
  );
}

// Logged-out experience: a marketing landing page that flips to the Auth form.
// Deep-link visitors (invite ?ref, or ?signin) skip straight to the form.
function LoggedOut() {
  const params = new URLSearchParams(window.location.search);
  const initial = params.get("ref")
    ? "signup"
    : params.get("signin") !== null
      ? "login"
      : null;
  const [authMode, setAuthMode] = useState(initial); // null = landing
  if (authMode) {
    return <Auth initialMode={authMode} onHome={() => setAuthMode(null)} />;
  }
  return <Landing onSignup={() => setAuthMode("signup")} onLogin={() => setAuthMode("login")} />;
}

function Shell() {
  const { isAuthed } = useApp();
  // The emailed verification link must work signed-in or out, so handle it
  // before the auth gate.
  if (window.location.pathname === "/verify-email") {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          <VerifyEmail />
        </Suspense>
      </ErrorBoundary>
    );
  }
  if (window.location.pathname === "/oauth/callback") {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          <OAuthCallback />
        </Suspense>
      </ErrorBoundary>
    );
  }
  if (window.location.pathname === "/verify-cert") {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          <VerifyCertificate />
        </Suspense>
      </ErrorBoundary>
    );
  }
  if (window.location.pathname === "/privacy" || window.location.pathname === "/terms") {
    const Page = window.location.pathname === "/privacy" ? Privacy : Terms;
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          <Page />
        </Suspense>
      </ErrorBoundary>
    );
  }
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingState />}>
        {isAuthed ? <AuthedApp /> : <LoggedOut />}
      </Suspense>
    </ErrorBoundary>
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
