import React from "react";

// Define props interface to accept an index for unique ID generation, visibility, and shrinking state
interface MistakeBubbleProps {
  index: number;
  isVisible?: boolean;
  isShrinking?: boolean;
}

const MistakeBubble: React.FC<MistakeBubbleProps> = ({ index, isVisible = true, isShrinking = false }) => {
  // Generate unique ID and class name for each bubble based on its index and state
  const className = `mistake-bubble ${isShrinking ? 'shrink' : ''}`;

  return (
    <span
      id={`mistake-bubble-${index}`}
      className={className}
      style={{
        visibility: isVisible ? 'visible' : 'hidden',
        opacity: isVisible ? 1 : 0
      }}
    ></span>
  );
};

export default MistakeBubble;
