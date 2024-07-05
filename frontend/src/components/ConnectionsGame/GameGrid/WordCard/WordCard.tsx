import React, { useState, useEffect } from "react";
import { useSelectedWords } from "../../../../context/SelectedWordsContext";
import { ANIMATION_DURATION } from "../../../../config/animationConfig";

interface WordCardProps {
  word: string;
  animate: boolean; // New prop to trigger animation
  delay: number; // New prop for animation delay
}

const WordCard: React.FC<WordCardProps> = ({ word, animate, delay }) => {
  const { selectedWords, addWord, removeWord } = useSelectedWords();
  const isSelected = selectedWords.includes(word);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (animate && isSelected) {
      const timer = setTimeout(() => setIsAnimating(true), delay);
      const resetTimer = setTimeout(() => setIsAnimating(false), delay + ANIMATION_DURATION); // Reset after animation
      return () => {
        clearTimeout(timer);
        clearTimeout(resetTimer);
      };
    }
  }, [animate, isSelected, delay]);

  const handleClick = (event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent event bubbling
    if (isSelected) {
      removeWord(word);
    } else {
      addWord(word);
    }
  };

  return (
    <div
      className={`word-card ${isSelected ? "selected" : ""} ${isAnimating ? "slide-up" : ""}`}
      onClick={handleClick}
    >
      {word}
    </div>
  );
};

export default WordCard;


