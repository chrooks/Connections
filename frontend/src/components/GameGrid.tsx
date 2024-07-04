import React from "react";
import WordCard from "./WordCard";
import useGameGrid from "../hooks/useGameGrid";

interface GameGridProps {
  onWordSelected: (word: string) => void;
}

/**
 * GameGrid component to display a grid of word cards.
 * Fetches the words using the useGameGrid hook and handles loading and error states.
 * 
 * @param {Object} props - The component props.
 * @param {Function} props.onWordSelected - Callback function to handle word selection.
 * 
 * @returns {JSX.Element} The rendered component.
 */
const GameGrid: React.FC<GameGridProps> = ({ onWordSelected }) => {
  const { words, loading, error } = useGameGrid();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="game-grid">
      {words.map((word, index) => (
        <WordCard key={index} word={word} onSelected={() => onWordSelected(word)} />
      ))}
    </div>
  );
};

export default GameGrid;
