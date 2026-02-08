import React, { useState } from "react";
import Navbar from "../Navbar/Navbar";
import ConnectionsGame from "../ConnectionsGame/ConnectionsGame";
import LandingPage from "../LandingPage/LandingPage";
import { SelectedWordsProvider } from "../../context/SelectedWordsContext";
import { useAuth } from "../../context/AuthContext";

const App: React.FC = () => {
  const { user, loading } = useAuth();
  // Track if user is playing as guest (not persisted)
  const [isGuestMode, setIsGuestMode] = useState(false);

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
        <Navbar showLowerNav={!showLandingPage} />
        {showLandingPage ? (
          <LandingPage onPlayAsGuest={handlePlayAsGuest} />
        ) : (
          <ConnectionsGame />
        )}
      </div>
    </SelectedWordsProvider>
  );
};

export default App;
