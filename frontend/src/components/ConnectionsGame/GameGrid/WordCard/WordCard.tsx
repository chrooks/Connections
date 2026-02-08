import React, { useState, useEffect } from "react";
import { useSelectedWords } from "../../../../context/SelectedWordsContext";
import { ANIMATION_DURATION } from "../../../../config/gameConfig";

// Animation phases for submission flow
export type AnimationPhase = "nudge" | "swap" | "fade" | null;

// Swap target info passed from parent
export interface SwapTarget {
  fromIndex: number; // Current grid position
  toIndex: number; // Target grid position
  delay: number; // Staggered delay for this swap
}

interface WordCardProps {
  word: string;
  gridIndex: number; // Current position in the grid (0-15)
  animationPhase: AnimationPhase; // Current animation phase
  nudgeDelay: number; // Staggered delay for nudge animation
  swapTarget: SwapTarget | null; // Swap animation target (if this card is swapping)
}

const WordCard: React.FC<WordCardProps> = ({ word, gridIndex: _gridIndex, animationPhase, nudgeDelay, swapTarget }) => {
  const { selectedWords, addWord, removeWord } = useSelectedWords();
  const isSelected = selectedWords.includes(word);
  const [currentAnimation, setCurrentAnimation] = useState<AnimationPhase>(null);
  const [swapOffset, setSwapOffset] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    // Handle nudge animation (only for selected cards)
    if (animationPhase === "nudge" && isSelected) {
      const startTimer = setTimeout(() => setCurrentAnimation("nudge"), nudgeDelay);
      const resetTimer = setTimeout(() => setCurrentAnimation(null), nudgeDelay + ANIMATION_DURATION);
      return () => {
        clearTimeout(startTimer);
        clearTimeout(resetTimer);
      };
    }

    // Handle swap animation (for any card that has a swap target)
    if (animationPhase === "swap" && swapTarget) {
      const { fromIndex, toIndex, delay } = swapTarget;

      // Calculate grid position difference
      const fromRow = Math.floor(fromIndex / 4);
      const fromCol = fromIndex % 4;
      const toRow = Math.floor(toIndex / 4);
      const toCol = toIndex % 4;

      // Card dimensions: ~9.875rem width (9.375 + 0.5 margin), ~5.5rem height (5 + 0.5 margin)
      const cardWidth = 9.875; // rem
      const cardHeight = 5.5; // rem

      const xOffset = (toCol - fromCol) * cardWidth;
      const yOffset = (toRow - fromRow) * cardHeight;

      // Start swap animation after staggered delay
      const startTimer = setTimeout(() => {
        setCurrentAnimation("swap");
        setSwapOffset({ x: xOffset, y: yOffset });
      }, delay);

      return () => {
        clearTimeout(startTimer);
      };
    }

    // Handle fade animation (only for selected cards that are now in target row)
    if (animationPhase === "fade" && isSelected) {
      setCurrentAnimation("fade");
      return;
    }

    // Reset when animation phase clears
    if (!animationPhase) {
      setCurrentAnimation(null);
      setSwapOffset(null);
    }
  }, [animationPhase, isSelected, nudgeDelay, swapTarget]);

  const handleClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    // Disable clicking during animations
    if (animationPhase) return;

    if (isSelected) {
      removeWord(word);
    } else {
      addWord(word);
    }
  };

  // Build class names based on current animation state
  const classNames = [
    "word-card",
    isSelected ? "selected" : "",
    currentAnimation === "nudge" ? "nudge" : "",
    currentAnimation === "swap" ? "swapping" : "",
    currentAnimation === "fade" ? "fading" : "",
  ].filter(Boolean).join(" ");

  // Build inline styles for swap transform
  const style: React.CSSProperties = {};
  if (swapOffset && currentAnimation === "swap") {
    style.transform = `translate(${swapOffset.x}rem, ${swapOffset.y}rem)`;
  }

  return (
    <div
      className={classNames}
      onClick={handleClick}
      style={style}
    >
      {word}
    </div>
  );
};

export default WordCard;
