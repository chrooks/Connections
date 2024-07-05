import React from "react";
import SettingsButton from "./SettingsButton";
import HelpButton from "./HelpButton";

const Navbar: React.FC = () => {
  return (
    <nav className="navbar">
      <div className="navbar-upper">
        <div className="container">
            <span className="connections-logo">Connections</span>
            <span className="version-logo">Chrooked Version</span>
        </div>
      </div>
      <div className="navbar-lower">
        <div className="container">
          <div className="nav-buttons">
            <SettingsButton />
            <HelpButton />
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
