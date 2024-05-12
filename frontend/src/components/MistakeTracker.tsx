import React from "react";

interface MistakeTrackerProps {
  // Define the props for the MistakeTracker component
  // e.g., remainingMistakes: number
}

const MistakeTracker: React.FC<MistakeTrackerProps> = (props) => {
  return (
    <div className="mistake-tracker my-2 d-flex align-items-center">
      <span className="mistake-tracker-label mx-1">Mistakes remaining:</span>
      <div className="mistake-tracker-bubbles d-flex">
        <span className="mistake-tracker-bubble"></span>
        <span className="mistake-tracker-bubble"></span>
        <span className="mistake-tracker-bubble"></span>
        <span className="mistake-tracker-bubble"></span>
      </div>
    </div>
  );
};

export default MistakeTracker;
