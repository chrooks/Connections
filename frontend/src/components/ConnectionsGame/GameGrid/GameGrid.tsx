import React, { useMemo } from "react";
import WordCard, { AnimationPhase, SwapTarget } from "./WordCard/WordCard";
import { useSelectedWords } from "../../../context/SelectedWordsContext";
import { ANIMATION_DELAY, SWAP_STAGGER } from "../../../config/gameConfig";

interface GameGridProps {
  words: string[];
  loading: boolean;
  error: string | null;
  animationPhase: AnimationPhase; // Current animation phase for selected cards
}

/**
 * Calculates swap targets for the position swap animation.
 * Selected cards not in target row swap with non-selected cards in target row.
 */
function calculateSwapTargets(
  words: string[],
  selectedWords: string[],
  targetRow: number
): Map<number, SwapTarget> {
  const swapTargets = new Map<number, SwapTarget>();

  // Target positions are the first 4 positions of the target row
  const targetPositions = [
    targetRow * 4,
    targetRow * 4 + 1,
    targetRow * 4 + 2,
    targetRow * 4 + 3,
  ];

  // Find selected cards that are NOT in the target row (need to move in)
  const selectedNotInTarget: number[] = [];
  words.forEach((word, index) => {
    if (selectedWords.includes(word) && !targetPositions.includes(index)) {
      selectedNotInTarget.push(index);
    }
  });

  // Find target positions occupied by non-selected cards (need to move out)
  const nonSelectedInTarget: number[] = [];
  targetPositions.forEach((pos) => {
    if (pos < words.length && !selectedWords.includes(words[pos])) {
      nonSelectedInTarget.push(pos);
    }
  });

  // Pair them up for swapping (in order)
  const swapCount = Math.min(selectedNotInTarget.length, nonSelectedInTarget.length);
  for (let i = 0; i < swapCount; i++) {
    const selectedPos = selectedNotInTarget[i];
    const targetPos = nonSelectedInTarget[i];
    const delay = i * SWAP_STAGGER;

    // Selected card moves to target position
    swapTargets.set(selectedPos, {
      fromIndex: selectedPos,
      toIndex: targetPos,
      delay,
    });

    // Non-selected card moves to where selected card was
    swapTargets.set(targetPos, {
      fromIndex: targetPos,
      toIndex: selectedPos,
      delay,
    });
  }

  return swapTargets;
}

/**
 * GameGrid component to display a grid of word cards.
 * Renders words in a 4x4 grid with animation support for submissions.
 */
const GameGrid: React.FC<GameGridProps> = ({ words, loading, error, animationPhase }) => {
  const { selectedWords } = useSelectedWords();

  // Calculate swap targets when in swap phase
  // Target row is always 0 - selected cards swap to the first row of remaining words
  const swapTargets = useMemo(() => {
    if (animationPhase === "swap") {
      return calculateSwapTargets(words, selectedWords, 0);
    }
    return new Map<number, SwapTarget>();
  }, [animationPhase, words, selectedWords]);

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
          key={word}
          word={word}
          gridIndex={index}
          animationPhase={animationPhase}
          nudgeDelay={selectedWords.indexOf(word) * ANIMATION_DELAY}
          swapTarget={swapTargets.get(index) || null}
        />
      ))}
    </div>
  );
};

export default GameGrid;
