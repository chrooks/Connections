import React from "react";
import MistakeBubble from "./MistakeBubble/MistakeBubble";

interface MistakeTrackerProps {
  // Define the props for the MistakeTracker component
  // e.g., remainingMistakes: number
}

const MistakeTracker: React.FC<MistakeTrackerProps> = () => {
  return (
    <div className="mistake-tracker">
      <span className="mistake-tracker-label">
        Mistakes remaining:
      </span>
      <div className="mistake-tracker-bubbles">
        <MistakeBubble />
        <MistakeBubble />
        <MistakeBubble />
        <MistakeBubble />
      </div>
    </div>
  );
};

export default MistakeTracker;
