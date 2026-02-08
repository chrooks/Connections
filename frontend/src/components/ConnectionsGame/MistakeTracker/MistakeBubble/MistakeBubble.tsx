import React from "react";

// Define props interface to accept an index for unique ID generation
interface MistakeBubbleProps {
  index: number;
}

const MistakeBubble: React.FC<MistakeBubbleProps> = ({ index }) => {
  // Generate unique ID for each bubble based on its index
  return <span id={`mistake-bubble-${index}`} className="mistake-bubble"></span>;
};

export default MistakeBubble;
