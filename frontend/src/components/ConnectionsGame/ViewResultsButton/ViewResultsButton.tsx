import React from "react";
import "./ViewResultsButton.scss";

interface ViewResultsButtonProps {
  onClick: () => void;
}

/**
 * Button that appears after game completion to open the results modal.
 * Fades in with animation when rendered.
 */
const ViewResultsButton: React.FC<ViewResultsButtonProps> = ({ onClick }) => {
  return (
    <button
      id="view-results-button"
      className="view-results-button"
      onClick={onClick}
    >
      View Results
    </button>
  );
};

export default ViewResultsButton;
