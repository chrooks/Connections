import React from "react";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGear } from '@fortawesome/free-solid-svg-icons';

const SettingsButton: React.FC = () => {
  const handleSettingsClick = () => {
    console.log("Settings button clicked");
  };

  return (
    <button onClick={handleSettingsClick} className="settings-button">
      <FontAwesomeIcon icon={faGear} size="lg" />
    </button>
  );
};

export default SettingsButton;

