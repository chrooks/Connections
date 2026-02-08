import React, { useEffect, useState } from "react";
import MistakeBubble from "./MistakeBubble/MistakeBubble";

interface MistakeTrackerProps {
  mistakesLeft: number;
}

const MistakeTracker: React.FC<MistakeTrackerProps> = ({ mistakesLeft }) => {
  const [prevMistakesLeft, setPrevMistakesLeft] = useState(mistakesLeft);

  useEffect(() => {
    // Check if the number of mistakes left has decreased
    if (mistakesLeft < prevMistakesLeft) {
      // Select all elements with the class "mistake-bubble"
      const bubbles = document.querySelectorAll(".mistake-bubble");
      // If there are any mistake bubbles
      if (bubbles.length > 0) {
        // Add the "shrink" class to the last bubble to trigger the shrink animation
        bubbles[bubbles.length - 1].classList.add("shrink");
      }
    }
    // Update the previous mistakes left state to the current mistakes left
    setPrevMistakesLeft(mistakesLeft);
  }, [mistakesLeft]); // Only re-run the effect when mistakesLeft changes

  return (
    <div className="mistake-tracker">
      <span className="mistake-tracker-label">
        Mistakes remaining:
      </span>
      <div className="mistake-tracker-bubbles">
        {Array.from({ length: mistakesLeft }).map((_, index) => (
          <MistakeBubble key={index} />
        ))}
      </div>
    </div>
  );
};

export default MistakeTracker;