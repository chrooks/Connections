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
    <nav id="navbar" className="navbar">
      <div id="navbar-upper" className="navbar-upper">
        <div className="container">
            <span id="connections-logo" className="connections-logo">Connections</span>
            <span id="version-logo" className="version-logo">Chrooked Version</span>
        </div>
      </div>

      {/* Only show lower navbar if showLowerNav is true */}
      {showLowerNav && (
        <div id="navbar-lower" className="navbar-lower">
          <div className="container">
            <div id="nav-buttons" className="nav-buttons">
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
