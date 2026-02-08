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
    <div className="landing-page">
      <div className="landing-content">
        <h1 className="landing-title">Connections</h1>
        <p className="landing-subtitle">Create four groups of four!</p>

        <div className="landing-description">
          <p>Find groups of four items that share something in common.</p>
          <p>Select four items and tap 'Submit' to check if your guess is correct.</p>
        </div>

        <div className="landing-actions">
          <button
            className="landing-btn landing-btn-primary"
            onClick={() => setShowAuthModal(true)}
          >
            Sign In / Sign Up
          </button>

          <button
            className="landing-btn landing-btn-secondary"
            onClick={onPlayAsGuest}
          >
            Play as Guest
          </button>

          <p className="landing-note">
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
