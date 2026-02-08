/**
 * Landing page component shown when user is not authenticated.
 * Provides options to sign in/sign up or play as a guest.
 */

import React, { useState } from "react";
import AuthModal from "../Auth/AuthModal";
import "./LandingPage.scss";

interface LandingPageProps {
  onPlayAsGuest: () => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ onPlayAsGuest }) => {
  const [showAuthModal, setShowAuthModal] = useState(false);

  return (
    <div id="landing-page" className="landing-page">
      <div id="landing-content" className="landing-content">
        <h1 id="landing-title" className="landing-title">Connections</h1>
        <p id="landing-subtitle" className="landing-subtitle">Create four groups of four!</p>

        <div id="landing-description" className="landing-description">
          <p>Find groups of four items that share something in common.</p>
          <p>Select four items and tap 'Submit' to check if your guess is correct.</p>
        </div>

        <div id="landing-actions" className="landing-actions">
          <button
            id="sign-in-sign-up-button"
            className="landing-btn landing-btn-primary"
            onClick={() => setShowAuthModal(true)}
          >
            Sign In / Sign Up
          </button>

          <button
            id="play-as-guest-button"
            className="landing-btn landing-btn-secondary"
            onClick={onPlayAsGuest}
          >
            Play as Guest
          </button>

          <p id="guest-mode-note" className="landing-note">
            Playing as a guest? Your progress won't be saved.
          </p>
        </div>
      </div>

      {/* Auth modal for login/signup */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />
    </div>
  );
};

export default LandingPage;
