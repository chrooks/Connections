import React, { useEffect, useState } from "react";
import GameGrid from "./GameGrid/GameGrid";
import MistakeTracker from "./MistakeTracker/MistakeTracker";
import ControlButtonBar from "./ControlButtonBar/ControlButtonBar";
import useGameGrid from "../../hooks/useGameGrid";
import { useSelectedWords } from "../../context/SelectedWordsContext";
import { ANIMATION_DURATION, ANIMATION_DELAY } from "../../config/animationConfig";

const ConnectionsGame: React.FC = () => {
  const { words, loading, error, shuffleWords } = useGameGrid();
  const { selectedWords, clearWords } = useSelectedWords();
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    // Set CSS variables dynamically
    document.documentElement.style.setProperty('--animation-duration', `${ANIMATION_DURATION}ms`);
    document.documentElement.style.setProperty('--animation-delay', `${ANIMATION_DELAY}ms`);
  }, []);

  const handleSubmit = () => {
    console.log('Selected words:', selectedWords);
    setAnimate(true);
    setTimeout(() => {
      setAnimate(false);
      clearWords();
      // Add your submit logic here
    }, selectedWords.length * ANIMATION_DELAY + ANIMATION_DURATION); // Adjust timing based on number of selected words
  };

  return (
    <div className="game container">
      <span className="game-instructions"> Create four groups of four!</span>
      <GameGrid words={words} loading={loading} error={error} animate={animate} />
      <MistakeTracker />
      <ControlButtonBar onShuffle={shuffleWords} onDeselect={() => { }} onSubmit={handleSubmit} />
    </div>
  );
};

export default ConnectionsGame;
