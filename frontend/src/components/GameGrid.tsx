import React from "react";
import WordCard from "./WordCard";

interface GameGridProps {
  words: string[];
  loading: boolean;
  error: string | null;
}

/**
 * GameGrid component to display a grid of word cards.
 * Fetches the words using the useGameGrid hook and handles loading and error states.
 * 
 * @param {Object} props - The component props.
 * @param {Array} props.words - The array of words to display.
 * @param {boolean} props.loading - The loading state.
 * @param {string} props.error - The error message.
 * @returns {JSX.Element} The rendered component.
 */
const GameGrid: React.FC<GameGridProps> = ({ words, loading, error }) => {

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="game-grid">
      {words.map((word) => (
        <WordCard word={word} />
      ))}
    </div>
  );
};

export default GameGrid;
