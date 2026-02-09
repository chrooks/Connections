import React, { useEffect, useState } from "react";
import MistakeBubble from "./MistakeBubble/MistakeBubble";

interface MistakeTrackerProps {
  mistakesLeft: number;
}

const MistakeTracker: React.FC<MistakeTrackerProps> = ({ mistakesLeft }) => {
  // Always render 4 bubbles, track which ones are shrinking
  const maxMistakes = 4;
  const [prevMistakesLeft, setPrevMistakesLeft] = useState(mistakesLeft);
  const [shrinkingIndex, setShrinkingIndex] = useState<number | null>(null);

  useEffect(() => {
    // When mistakes decrease, trigger shrink animation on the bubble that should disappear
    if (mistakesLeft < prevMistakesLeft) {
      // The bubble at index mistakesLeft should shrink (the last visible one)
      setShrinkingIndex(mistakesLeft);

      // After animation completes, clear shrinking state
      setTimeout(() => {
        setShrinkingIndex(null);
      }, 300); // Match animation duration
    }
    setPrevMistakesLeft(mistakesLeft);
  }, [mistakesLeft, prevMistakesLeft]);

  return (
    <div id="mistake-tracker" className="mistake-tracker">
      <span id="mistake-tracker-label" className="mistake-tracker-label">
        Mistakes remaining:
      </span>
      <div id="mistake-tracker-bubbles" className="mistake-tracker-bubbles">
        {Array.from({ length: maxMistakes }).map((_, index) => {
          // Bubble is visible if index is less than mistakesLeft or if it's currently shrinking
          const isVisible = index < mistakesLeft || index === shrinkingIndex;
          const isShrinking = index === shrinkingIndex;
          return (
            <MistakeBubble
              key={index}
              index={index}
              isVisible={isVisible}
              isShrinking={isShrinking}
            />
          );
        })}
      </div>
    </div>
  );
};

export default MistakeTracker;