import React, { useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUserPlus } from "@fortawesome/free-solid-svg-icons";
import SettingsButton from "./SettingsButton";
import AuthModal from "../Auth/AuthModal";
import UserMenu from "../Auth/UserMenu";
import { useAuth } from "../../context/AuthContext";

interface NavbarProps {
  showLowerNav?: boolean; // Optional prop to control lower navbar visibility
  onNavigateToProfile?: () => void; // Callback to navigate to the profile view
  onNavigateToAdmin?: () => void; // Callback to navigate to the admin view (admin users only)
}

const Navbar: React.FC<NavbarProps> = ({ showLowerNav = true, onNavigateToProfile, onNavigateToAdmin }) => {
  const { user, loading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  return (
    <nav id="navbar" className="navbar">
      <div id="navbar-upper" className="navbar-upper">
        <div className="container">
            <span id="connections-logo" className="connections-logo">Connections</span>
            <span id="version-logo" className="version-logo">Chrooked Edition</span>
        </div>
      </div>

      {/* Only show lower navbar if showLowerNav is true */}
      {showLowerNav && (
        <div id="navbar-lower" className="navbar-lower">
          <div className="container">
            <div id="nav-buttons" className="nav-buttons">
              <SettingsButton />

              {/* Auth section - show user menu when authenticated, sign-up button for guests */}
              {!loading && user && (
                <UserMenu
                  onNavigateToProfile={onNavigateToProfile}
                  onNavigateToAdmin={onNavigateToAdmin}
                />
              )}
              {!loading && !user && (
                <button
                  id="navbar-signup-button"
                  className="user-menu-icon"
                  onClick={() => setShowAuthModal(true)}
                  aria-label="Sign up or sign in"
                  title="Sign up / Sign in"
                >
                  <FontAwesomeIcon icon={faUserPlus} />
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Auth modal for login/signup */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />
    </nav>
  );
};

export default Navbar;
