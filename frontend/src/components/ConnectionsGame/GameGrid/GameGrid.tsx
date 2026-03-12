import React, { useMemo } from "react";
import WordCard, { AnimationPhase, SwapTarget } from "./WordCard/WordCard";
import { useSelectedWords } from "../../../context/SelectedWordsContext";
import { ANIMATION_DELAY, SWAP_STAGGER } from "../../../config/gameConfig";

interface GameGridProps {
  words: string[];
  loading: boolean;
  error: string | null;
  poolExhausted: boolean;
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
const GameGrid: React.FC<GameGridProps> = ({ words, loading, error, poolExhausted, animationPhase }) => {
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
    return (
      <div id="game-grid-loading" className="game-grid">
        {Array.from({ length: 16 }).map((_, i) => (
          <div key={i} className="word-card word-card--skeleton" />
        ))}
      </div>
    );
  }

  if (poolExhausted) {
    return (
      <div id="pool-exhausted-container" className="pool-exhausted-container">
        <p id="pool-exhausted-emoji" className="pool-exhausted-emoji">🧩</p>
        <h2 id="pool-exhausted-heading" className="pool-exhausted-heading">You're all caught up!</h2>
        <p id="pool-exhausted-message" className="pool-exhausted-message">
          You've completed every available puzzle. Check back soon — new ones are on the way!
        </p>
      </div>
    );
  }

  if (error) {
    return <div id="game-grid-error">Error: {error}</div>;
  }

  return (
    <div id="game-grid" className="game-grid">
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
