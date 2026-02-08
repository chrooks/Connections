import React, { useEffect, useState, useMemo } from "react";
import GameGrid from "./GameGrid/GameGrid";
import MistakeTracker from "./MistakeTracker/MistakeTracker";
import ControlButtonBar from "./ControlButtonBar/ControlButtonBar";
import SolvedConnection from "./SolvedConnection/SolvedConnection";
import useGameState from "../../hooks/useGameState";
import useSubmitGuess from "../../hooks/useSubmitGuess";
import { useSelectedWords } from "../../context/SelectedWordsContext";
import { ANIMATION_DURATION, ANIMATION_DELAY, SWAP_DURATION, SWAP_STAGGER, FADE_DURATION, GAME_ID } from "../../config/gameConfig";
import { AnimationPhase } from "./GameGrid/WordCard/WordCard";
import { ToastContainer } from "react-toastify";
import 'react-toastify/dist/ReactToastify.css';

// Type for a connection object from the API
interface Connection {
  relationship: string;
  words: string[];
  guessed: boolean;
}

const ConnectionsGame: React.FC = () => {
  const [mistakesLeft, setMistakesLeft] = useState<number>(4);
  // Track the order in which connections were solved (array of connection indices)
  const [solvedOrder, setSolvedOrder] = useState<number[]>([]);
  // Track the current grid word order (preserves order after swaps)
  const [gridWords, setGridWords] = useState<string[]>([]);
  const { words, loading, error, connections } = useGameState(setMistakesLeft);
  const { selectedWords, clearWords } = useSelectedWords();
  // Animation phase: null = none, "nudge" = initial bump, "swap" = swapping positions, "fade" = fading out
  const [animationPhase, setAnimationPhase] = useState<AnimationPhase>(null);
  const { submitGuess } = useSubmitGuess(setMistakesLeft);

  // Initialize gridWords from words when they load
  useEffect(() => {
    if (words.length > 0 && gridWords.length === 0) {
      setGridWords(words);
    }
  }, [words, gridWords.length]);

  // Get solved connections in the order they were guessed (not by difficulty)
  const solvedConnections = useMemo(() => {
    return solvedOrder.map(index => (connections as Connection[])[index]);
  }, [connections, solvedOrder]);

  // Filter out words that belong to solved connections (use gridWords to preserve order)
  const remainingWords = useMemo(() => {
    const solvedWords = new Set(solvedConnections.flatMap(conn => conn.words));
    return gridWords.filter(word => !solvedWords.has(word));
  }, [gridWords, solvedConnections]);

  useEffect(() => {
    document.documentElement.style.setProperty('--animation-duration', `${ANIMATION_DURATION}ms`);
    document.documentElement.style.setProperty('--animation-delay', `${ANIMATION_DELAY}ms`);
  }, []);

  // Shuffle remaining words using Fisher-Yates algorithm
  const handleShuffle = () => {
    setGridWords(prev => {
      const shuffled = [...prev];
      // Only shuffle the remaining (unsolved) words while keeping solved words in place
      const solvedWordsSet = new Set(solvedConnections.flatMap(conn => conn.words));
      const remainingIndices = prev
        .map((word, idx) => ({ word, idx }))
        .filter(({ word }) => !solvedWordsSet.has(word))
        .map(({ idx }) => idx);

      // Fisher-Yates shuffle on remaining indices
      for (let i = remainingIndices.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const idxA = remainingIndices[i];
        const idxB = remainingIndices[j];
        [shuffled[idxA], shuffled[idxB]] = [shuffled[idxB], shuffled[idxA]];
      }
      return shuffled;
    });
  };

  const handleSubmit = async () => {
    console.log('Selected words:', selectedWords);

    // Calculate nudge animation duration (staggered delay for all 4 cards + animation itself)
    const nudgeDuration = selectedWords.length * ANIMATION_DELAY + ANIMATION_DURATION;

    // Start nudge animation and API call in parallel
    setAnimationPhase("nudge");
    const resultPromise = submitGuess(GAME_ID, selectedWords);

    // Wait for nudge animation to complete
    await new Promise(resolve => setTimeout(resolve, nudgeDuration));
    setAnimationPhase(null);

    // Wait for API result
    const result = await resultPromise;

    if (result?.isCorrect) {
      // Calculate swap pairs (same logic as GameGrid)
      const targetPositions = [0, 1, 2, 3];

      // Find selected cards not in target row
      const selectedNotInTarget: number[] = [];
      remainingWords.forEach((word, index) => {
        if (selectedWords.includes(word) && !targetPositions.includes(index)) {
          selectedNotInTarget.push(index);
        }
      });

      // Find target positions with non-selected cards
      const nonSelectedInTarget: number[] = [];
      targetPositions.forEach((pos) => {
        if (pos < remainingWords.length && !selectedWords.includes(remainingWords[pos])) {
          nonSelectedInTarget.push(pos);
        }
      });

      const swapsNeeded = Math.min(selectedNotInTarget.length, nonSelectedInTarget.length);

      // Phase 1: Swap animation - cards move to target row
      setAnimationPhase("swap");
      const swapDuration = swapsNeeded * SWAP_STAGGER + SWAP_DURATION;
      await new Promise(resolve => setTimeout(resolve, swapDuration));

      // Phase 2: Fade animation - selected cards in target row fade out
      setAnimationPhase("fade");
      await new Promise(resolve => setTimeout(resolve, FADE_DURATION));

      // Phase 3: Update state - apply swaps and remove solved words
      // We delay gridWords update until after fade so the re-render doesn't cause a visual jump
      setAnimationPhase(null);

      // Apply swaps to gridWords to preserve visual order
      const newGridWords = [...gridWords];
      const solvedWords = new Set(solvedConnections.flatMap(conn => conn.words));
      // Get indices in the full gridWords array (not just remainingWords)
      const gridIndices = gridWords
        .map((word, idx) => ({ word, idx }))
        .filter(({ word }) => !solvedWords.has(word));

      for (let i = 0; i < swapsNeeded; i++) {
        const fromRemainingIdx = selectedNotInTarget[i];
        const toRemainingIdx = nonSelectedInTarget[i];
        // Convert remaining indices to grid indices
        const fromGridIdx = gridIndices[fromRemainingIdx].idx;
        const toGridIdx = gridIndices[toRemainingIdx].idx;
        // Swap in the grid
        [newGridWords[fromGridIdx], newGridWords[toGridIdx]] =
          [newGridWords[toGridIdx], newGridWords[fromGridIdx]];
      }
      setGridWords(newGridWords);
      // Find which connection was just solved (newly true in guessedConnections)
      const newlySolvedIndex = result.guessedConnections.findIndex(
        (guessed, idx) => guessed && !solvedOrder.includes(idx)
      );
      if (newlySolvedIndex !== -1) {
        setSolvedOrder(prev => [...prev, newlySolvedIndex]);
      }
      clearWords();
    } else {
      // Incorrect or duplicate guess: just clear selection
      clearWords();
    }
  };

  return (
    <div className="game container">
      <ToastContainer />
      <span className="game-instructions"> Create four groups of four!</span>
      {/* Render solved connections above the grid */}
      <div className="solved-connections-container">
        {solvedConnections.map((conn) => {
          // Find original index to determine color
          const originalIndex = (connections as Connection[]).findIndex(c => c.relationship === conn.relationship);
          return (
            <SolvedConnection
              key={conn.relationship}
              category={conn.relationship}
              words={conn.words}
              index={originalIndex}
            />
          );
        })}
      </div>
      {/* Grid shows only remaining unsolved words */}
      <GameGrid words={remainingWords} loading={loading} error={error} animationPhase={animationPhase} />
      <MistakeTracker mistakesLeft={mistakesLeft} />
      <ControlButtonBar onShuffle={handleShuffle} onDeselect={() => { }} onSubmit={handleSubmit} />
    </div>
  );
};

export default ConnectionsGame;