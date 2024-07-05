import React from "react";
import WordCard from "./WordCard/WordCard";
import { useSelectedWords } from "../../../context/SelectedWordsContext";
import { ANIMATION_DELAY } from "../../../config/animationConfig";

interface GameGridProps {
  words: string[];
  loading: boolean;
  error: string | null;
  animate: boolean; // New prop to trigger animation
}

/**
 * GameGrid component to display a grid of word cards.
 * Fetches the words using the useGameGrid hook and handles loading and error states.
 * 
 * @param {Object} props - The component props.
 * @param {Array} props.words - The array of words to display.
 * @param {boolean} props.loading - The loading state.
 * @param {string} props.error - The error message.
 * @param {boolean} props.animate - Whether to animate the word cards.
 * @returns {JSX.Element} The rendered component.
 */
const GameGrid: React.FC<GameGridProps> = ({ words, loading, error, animate }) => {
  const { selectedWords } = useSelectedWords();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="game-grid">
      {words.map((word, index) => (
        <WordCard
          key={index}
          word={word}
          animate={animate}
          delay={selectedWords.indexOf(word) * ANIMATION_DELAY} // Delay based on the order of selection
        />
      ))}
    </div>
  );
};

export default GameGrid;
