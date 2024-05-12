import React from "react";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faQuestionCircle } from '@fortawesome/free-solid-svg-icons';

const HelpButton: React.FC = () => {
  const handleHelpClick = () => {
    console.log("Help button clicked");
  };

  return (
    <button onClick={handleHelpClick} className="help-button">
      <FontAwesomeIcon icon={faQuestionCircle} size="lg"  />
    </button>
  );
};

export default HelpButton;

