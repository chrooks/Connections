import React from "react";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGear } from '@fortawesome/free-solid-svg-icons';

const SettingsButton: React.FC = () => {
  return (
    <button
      id="settings-button"
      className="settings-button"
      disabled
      aria-label="Settings (not yet implemented)"
      title="Not yet implemented"
    >
      <FontAwesomeIcon icon={faGear} size="lg" />
    </button>
  );
};

export default SettingsButton;
