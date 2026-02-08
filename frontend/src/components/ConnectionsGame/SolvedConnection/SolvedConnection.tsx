import React from "react";

// Connection difficulty colors matching NYT Connections (yellow, green, blue, purple)
const DIFFICULTY_COLORS = ["#f9df6d", "#a0c35a", "#b0c4ef", "#ba81c5"];

interface SolvedConnectionProps {
  category: string; // The relationship/category name
  words: string[]; // The four words in this connection
  index: number; // Index determines the color (0=yellow, 1=green, 2=blue, 3=purple)
}

/**
 * SolvedConnection component displays a solved connection group.
 * Shows the category name and the four words that belong to it.
 * Background color is determined by the connection's difficulty index.
 */
const SolvedConnection: React.FC<SolvedConnectionProps> = ({ category, words, index }) => {
  // Get background color based on difficulty index, defaulting to yellow if out of range
  const backgroundColor = DIFFICULTY_COLORS[index] || DIFFICULTY_COLORS[0];

  return (
    <div
      className="solved-connection"
      style={{ backgroundColor }}
    >
      {/* Category name displayed prominently */}
      <span className="solved-connection__category">{category}</span>
      {/* Words displayed as comma-separated list */}
      <span className="solved-connection__words">{words.join(", ")}</span>
    </div>
  );
};

export default SolvedConnection;
