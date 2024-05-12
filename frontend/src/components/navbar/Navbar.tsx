import React from "react";
import SettingsButton from "./nav-buttons/SettingsButton";
import HelpButton from "./nav-buttons/HelpButton";

const Navbar: React.FC = () => {
  return (
    <nav className="navbar">
      <div className="navbar-upper w-100">
        <div className="container py-3">
            <span className="connections-logo">Connections</span>
            <span className="version-logo">Chrooked Version</span>
        </div>
      </div>
      <div className="navbar-lower w-100">
        <div className="container d-flex justify-content-end">
          <div className="nav-buttons ">
            <SettingsButton />
            <HelpButton />
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
