import React, { useState } from "react";
import SettingsButton from "./SettingsButton";
import HelpButton from "./HelpButton";
import AuthModal from "../Auth/AuthModal";
import UserMenu from "../Auth/UserMenu";
import { useAuth } from "../../context/AuthContext";

interface NavbarProps {
  showLowerNav?: boolean; // Optional prop to control lower navbar visibility
}

const Navbar: React.FC<NavbarProps> = ({ showLowerNav = true }) => {
  const { user, loading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  return (
    <nav className="navbar">
      <div className="navbar-upper">
        <div className="container">
            <span className="connections-logo">Connections</span>
            <span className="version-logo">Chrooked Version</span>
        </div>
      </div>

      {/* Only show lower navbar if showLowerNav is true */}
      {showLowerNav && (
        <div className="navbar-lower">
          <div className="container">
            <div className="nav-buttons">
              <SettingsButton />
              <HelpButton />

              {/* Auth section - show user menu when authenticated */}
              {!loading && user && <UserMenu />}
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
