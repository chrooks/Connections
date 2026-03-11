import React, { useState } from "react";
import Navbar from "../Navbar/Navbar";
import ConnectionsGame from "../ConnectionsGame/ConnectionsGame";
import LandingPage from "../LandingPage/LandingPage";
import ProfileScreen from "../ProfileScreen/ProfileScreen";
import { SelectedWordsProvider } from "../../context/SelectedWordsContext";
import { useAuth } from "../../context/AuthContext";

// Top-level view — 'profile' is only reachable when authenticated
type AppView = "game" | "profile";

const App: React.FC = () => {
  const { user, loading } = useAuth();
  // Track if user is playing as guest (not persisted)
  const [isGuestMode, setIsGuestMode] = useState(false);
  const [currentView, setCurrentView] = useState<AppView>("game");

  // Handle playing as guest
  const handlePlayAsGuest = () => {
    setIsGuestMode(true);
  };

  // Show landing page if not authenticated and not in guest mode
  const showLandingPage = !user && !isGuestMode;

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div id="app-container" className="app">
        <Navbar showLowerNav={false} />
        <div id="loading-container" className="loading-container">
          <p id="loading-text">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <SelectedWordsProvider>
      <div id="app-container" className="app">
        <Navbar
          showLowerNav={!showLandingPage}
          onNavigateToProfile={() => setCurrentView("profile")}
        />
        {showLandingPage ? (
          <LandingPage onPlayAsGuest={handlePlayAsGuest} />
        ) : currentView === "profile" ? (
          <ProfileScreen onBack={() => setCurrentView("game")} />
        ) : (
          <ConnectionsGame />
        )}
      </div>
    </SelectedWordsProvider>
  );
};

export default App;
