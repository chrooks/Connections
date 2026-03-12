import React, { useEffect, useState, useMemo } from "react";
import GameGrid from "./GameGrid/GameGrid";
import MistakeTracker from "./MistakeTracker/MistakeTracker";
import ControlButtonBar from "./ControlButtonBar/ControlButtonBar";
import SolvedConnection from "./SolvedConnection/SolvedConnection";
import ViewResultsButton from "./ViewResultsButton/ViewResultsButton";
import ResultsModal from "./ResultsModal/ResultsModal";
import useGameState from "../../hooks/useGameState";
import useSubmitGuess from "../../hooks/useSubmitGuess";
import { useSelectedWords } from "../../context/SelectedWordsContext";
import { useAuth } from "../../context/AuthContext";
import { ANIMATION_DURATION, ANIMATION_DELAY, SWAP_DURATION, SWAP_STAGGER, FADE_DURATION } from "../../config/gameConfig";
import { AnimationPhase } from "./GameGrid/WordCard/WordCard";
import { ToastContainer } from "react-toastify";
import 'react-toastify/dist/ReactToastify.css';
import useTimer from "../../hooks/useTimer";
import PuzzleTimer from "./PuzzleTimer/PuzzleTimer";
import ForfeitButton from "./ForfeitButton/ForfeitButton";
import ForfeitConfirmModal from "./ForfeitConfirmModal/ForfeitConfirmModal";
import { apiPost } from "../../lib/api";
import { adminApiPost } from "../../lib/adminApi";

// Type for a connection object from the API
interface Connection {
  relationship: string;
  words: string[];
  guessed: boolean;
}

// Type for tracking guess history for results modal
interface GuessHistoryEntry {
  guess: string[];           // The 4 words guessed
  isCorrect: boolean;        // Whether guess was correct
  connectionIndex: number | null;  // Which connection (0-3), null if incorrect
}

interface ConnectionsGameProps {
  /** When set, loads this specific game session instead of calling /generate-grid.
   *  Used for admin play-test mode to review a specific puzzle. */
  reviewGameId?: string | null;
  /** The puzzle being reviewed — used to call approve/reject from the end screen. */
  reviewPuzzleId?: string;
  /** Which admin tab the puzzle came from — determines whether to show Approve or Reject. */
  reviewTab?: "rejected" | "approved";
  /** Called when the admin clicks "Back to Admin" after a review game ends. */
  onReviewComplete?: () => void;
  /** Navigates to the profile/stats screen — shown on the pool exhausted screen for logged-in users. */
  onNavigateToProfile?: () => void;
}

const ConnectionsGame: React.FC<ConnectionsGameProps> = ({ reviewGameId = null, reviewPuzzleId, reviewTab, onReviewComplete, onNavigateToProfile }) => {
  const { user } = useAuth();
  const [mistakesLeft, setMistakesLeft] = useState<number>(4);
  // Track the order in which connections were solved (array of connection indices)
  const [solvedOrder, setSolvedOrder] = useState<number[]>([]);
  // Track the current grid word order (preserves order after swaps)
  const [gridWords, setGridWords] = useState<string[]>([]);
  const { words, loading, error, poolExhausted, connections, revealConnection, gameId, puzzleNumber, startNewGame, initialSolvedIndicesRef, initialPreviousGuessesRef } = useGameState(setMistakesLeft, reviewGameId);
  const { selectedWords, addWord, clearWords } = useSelectedWords();
  // Animation phase: null = none, "nudge" = initial bump, "swap" = swapping positions, "fade" = fading out
  const [animationPhase, setAnimationPhase] = useState<AnimationPhase>(null);
  const { submitGuess } = useSubmitGuess(setMistakesLeft);

  // Game completion state for end-game experience
  const [gameComplete, setGameComplete] = useState<boolean>(false);
  const [gameResult, setGameResult] = useState<'WIN' | 'LOSS' | 'FORFEIT' | null>(null);
  const [showEndScreen, setShowEndScreen] = useState<boolean>(false);
  const [isResultsModalOpen, setIsResultsModalOpen] = useState<boolean>(false);
  const [isForfeitModalOpen, setIsForfeitModalOpen] = useState<boolean>(false);
  // Track guess history for results visualization
  const [guessHistory, setGuessHistory] = useState<GuessHistoryEntry[]>([]);
  // Tracks in-flight approve/reject action from the review end screen
  const [isReviewActioning, setIsReviewActioning] = useState(false);

  // Timer: ticks while the game is in progress, resets when a new game starts.
  // `gameId` is used as the reset key — it changes whenever a new session loads.
  const timerActive = !loading && words.length > 0 && !gameComplete;
  const { elapsed: elapsedSeconds, elapsedRef: elapsedSecondsRef } = useTimer(timerActive, gameId);

  // When the game ends, persist the elapsed time to the backend.
  useEffect(() => {
    if (!gameComplete || !gameId) return;
    apiPost("/record-completion-time", {
      gameId,
      timeSeconds: elapsedSecondsRef.current,
    }).catch(err => console.error("Failed to record completion time:", err));
  }, [gameComplete]); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize or reset gridWords whenever a new game's words arrive.
  // Using only `words` as the dependency ensures re-sync after HMR or a new game.
  useEffect(() => {
    if (words.length > 0) {
      setGridWords(words);
      // Read solved indices from the ref — it was written synchronously BEFORE
      // setWords was called in fetchGameState, so by the time this effect runs
      // it always holds the value for the current game (never the previous one).
      setSolvedOrder(initialSolvedIndicesRef.current);
      // Reconstruct guess history from server data so the results modal shows
      // all guesses even after a page refresh. correctness is derived by checking
      // whether all 4 words in a past guess belong to the same connection group.
      const restoredHistory = initialPreviousGuessesRef.current.map(guess => {
        const matchingIdx = (connections as Connection[]).findIndex(
          conn => conn.words && guess.every(w => conn.words.includes(w))
        );
        return {
          guess,
          isCorrect: matchingIdx !== -1,
          connectionIndex: matchingIdx !== -1 ? matchingIdx : null,
        };
      });
      setGuessHistory(restoredHistory);
      setGameComplete(false);
      setGameResult(null);
      setShowEndScreen(false);
    }
  }, [words]); // eslint-disable-line react-hooks/exhaustive-deps

  // Get solved connections in the order they were guessed (not by difficulty).
  // Filter out any stripped connections (no words) that may appear briefly during
  // puzzle transitions before solvedOrder resets to match the new game.
  const solvedConnections = useMemo(() => {
    return solvedOrder
      .map(index => (connections as Connection[])[index])
      .filter(conn => conn?.words);
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

  // Detect game completion (win or loss)
  useEffect(() => {
    if (connections.length === 0) return; // Wait for connections to load

    const allSolved = solvedOrder.length === 4;
    const outOfMistakes = mistakesLeft === 0 && !allSolved;

    if (allSolved && !gameComplete) {
      setGameComplete(true);
      setGameResult('WIN');
      setShowEndScreen(true); // Show end screen immediately for wins
    } else if (outOfMistakes && !gameComplete) {
      setGameComplete(true);
      setGameResult('LOSS');
      // showEndScreen will be set to true after auto-reveal completes
    }
  }, [solvedOrder.length, mistakesLeft, connections.length, gameComplete]);

  // Trigger auto-reveal animation sequence when game ends in loss or forfeit
  useEffect(() => {
    if (gameResult === 'LOSS' || gameResult === 'FORFEIT') {
      autoRevealConnections();
    }
  }, [gameResult]);

  // Auto-reveal unsolved connections when game ends in loss
  const autoRevealConnections = async () => {
    // The game is now LOSS/FORFEIT, so /game-status returns full connection data.
    // Fetch it to replace the stripped local state before running the animation.
    let fullConnections = connections as Connection[];
    if (gameId) {
      try {
        const res = await apiPost("/game-status", { gameId });
        const json = await res.json();
        if (json.data?.connections) {
          fullConnections = json.data.connections;
          json.data.connections.forEach((conn: any, idx: number) => {
            if (conn.words) revealConnection(idx, conn);
          });
        }
      } catch {
        // Fall back to local state; animation may be incomplete
      }
    }

    // Get unsolved connection indices in difficulty order (0-3 = yellow, green, blue, purple)
    const unsolvedIndices = fullConnections
      .map((conn, idx) => ({ conn, idx }))
      .filter(({ idx }) => !solvedOrder.includes(idx))
      .map(({ idx }) => idx)
      .sort((a, b) => a - b);

    console.log('Auto-revealing connections:', unsolvedIndices);

    // Create a working copy of gridWords to track changes
    let currentGridWords = [...gridWords];
    let currentSolvedOrder = [...solvedOrder];

    // Reveal each connection sequentially
    for (const connIdx of unsolvedIndices) {
      const connection = fullConnections[connIdx];
      const targetWords = connection.words;

      // Calculate which remaining words we're working with
      const currentSolvedWords = new Set(
        currentSolvedOrder.map(idx => fullConnections[idx].words).flat()
      );
      const currentRemainingWords = currentGridWords.filter(word => !currentSolvedWords.has(word));

      // Calculate swap pairs to move target words to top row
      const targetPositions = [0, 1, 2, 3];
      const selectedNotInTarget: number[] = [];
      const nonSelectedInTarget: number[] = [];

      currentRemainingWords.forEach((word, index) => {
        if (targetWords.includes(word) && !targetPositions.includes(index)) {
          selectedNotInTarget.push(index);
        }
      });

      targetPositions.forEach((pos) => {
        if (pos < currentRemainingWords.length && !targetWords.includes(currentRemainingWords[pos])) {
          nonSelectedInTarget.push(pos);
        }
      });

      const swapsNeeded = Math.min(selectedNotInTarget.length, nonSelectedInTarget.length);
      const swapDuration = swapsNeeded * SWAP_STAGGER + SWAP_DURATION;

      // Select the target words so they animate during swap/fade
      targetWords.forEach(word => addWord(word));

      // Swap phase
      setAnimationPhase("swap");
      await new Promise(resolve => setTimeout(resolve, swapDuration));

      // Fade phase
      setAnimationPhase("fade");
      await new Promise(resolve => setTimeout(resolve, FADE_DURATION));

      setAnimationPhase(null);

      // Clear selection after animation completes
      clearWords();

      // Apply swaps to gridWords
      const newGridWords = [...currentGridWords];
      const gridIndices = currentGridWords
        .map((word, idx) => ({ word, idx }))
        .filter(({ word }) => !currentSolvedWords.has(word));

      for (let i = 0; i < swapsNeeded; i++) {
        const fromRemainingIdx = selectedNotInTarget[i];
        const toRemainingIdx = nonSelectedInTarget[i];
        const fromGridIdx = gridIndices[fromRemainingIdx].idx;
        const toGridIdx = gridIndices[toRemainingIdx].idx;
        [newGridWords[fromGridIdx], newGridWords[toGridIdx]] =
          [newGridWords[toGridIdx], newGridWords[fromGridIdx]];
      }

      currentGridWords = newGridWords;
      currentSolvedOrder = [...currentSolvedOrder, connIdx];

      setGridWords(newGridWords);
      setSolvedOrder(currentSolvedOrder);

      // Delay before next connection reveal
      await new Promise(resolve => setTimeout(resolve, 800));
    }

    // After all connections are revealed, show the end screen
    setShowEndScreen(true);
  };

  // Handle forfeit confirmation: persist to backend then trigger the loss animation
  const handleForfeitConfirm = async () => {
    setIsForfeitModalOpen(false);
    if (!gameId) return;
    try {
      const res = await apiPost("/forfeit-game", { gameId });
      if (!res.ok) {
        // 409 means the game already ended naturally — treat as a normal loss
        setGameComplete(true);
        setGameResult('LOSS');
        return;
      }
    } catch (err) {
      console.error("Failed to record forfeit:", err);
    }
    setGameComplete(true);
    setGameResult('FORFEIT');
  };

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

  // Called from the review end screen — approves or rejects the puzzle being tested,
  // then navigates back to the admin screen.
  const handleReviewAction = async (action: "approve" | "reject") => {
    if (!reviewPuzzleId) return;
    setIsReviewActioning(true);
    try {
      const res = await adminApiPost(`/puzzles/${reviewPuzzleId}/${action}`);
      if (!res.ok) {
        const json = await res.json();
        throw new Error(json.message ?? "Action failed");
      }
      const { toast } = await import("react-toastify");
      toast.success(`Puzzle ${action === "approve" ? "approved" : "rejected"}`);
      onReviewComplete?.();
    } catch (err) {
      const { toast } = await import("react-toastify");
      toast.error(err instanceof Error ? err.message : "Action failed");
      setIsReviewActioning(false);
    }
  };

  const handleSubmit = async () => {
    console.log('Selected words:', selectedWords);

    // Calculate nudge animation duration (staggered delay for all 4 cards + animation itself)
    const nudgeDuration = selectedWords.length * ANIMATION_DELAY + ANIMATION_DURATION;

    // Start nudge animation and API call in parallel
    setAnimationPhase("nudge");
    const resultPromise = submitGuess(gameId!, selectedWords);

    // Wait for nudge animation to complete
    await new Promise(resolve => setTimeout(resolve, nudgeDuration));
    setAnimationPhase(null);

    // Wait for API result
    const result = await resultPromise;

    // Track guess in history for results modal
    if (result?.isNewGuess) {
      const connectionIndex = result.isCorrect
        ? result.guessedConnections.findIndex((guessed, idx) =>
            guessed && !solvedOrder.includes(idx))
        : null;

      setGuessHistory(prev => [...prev, {
        guess: [...selectedWords],
        isCorrect: result.isCorrect,
        connectionIndex
      }]);
    }

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
        // Reveal the full connection data before updating solvedOrder.
        // game-status strips unguessed connections to prevent cheating, so the
        // local connections state has no data for this index yet. The backend
        // returns the solved connection in the submit-guess response for exactly this.
        if (result.solvedConnection) {
          revealConnection(newlySolvedIndex, result.solvedConnection);
        }
        setSolvedOrder(prev => [...prev, newlySolvedIndex]);
      }
      clearWords();
    }
    // Incorrect or duplicate guess: keep selection so the player can swap one word and retry
  };

  if (poolExhausted) {
    return (
      <div id="connections-game-container" className="game container">
        <ToastContainer position="top-center" theme="dark" hideProgressBar closeButton={false} icon={false} autoClose={1500} />
        <div id="pool-exhausted-container" className="pool-exhausted-container">
          <p id="pool-exhausted-emoji" className="pool-exhausted-emoji">🧩</p>
          <h2 id="pool-exhausted-heading" className="pool-exhausted-heading">You're all caught up!</h2>
          <p id="pool-exhausted-message" className="pool-exhausted-message">
            You've completed every available puzzle. Check back soon — new ones are on the way!
          </p>
          {user && onNavigateToProfile && (
            <>
              <p id="pool-exhausted-stats-prompt" className="pool-exhausted-stats-prompt">
                In the meantime, check out your stats!
              </p>
              <button
                id="pool-exhausted-profile-button"
                className="pool-exhausted-profile-button"
                onClick={onNavigateToProfile}
              >
                View My Stats
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div id="connections-game-container" className="game container">
      <ToastContainer position="top-center" theme="dark" hideProgressBar closeButton={false} icon={false} autoClose={1500} />
      {/* Show timer once words are loaded; stays visible (frozen) on end screen */}
      {loading
        ? <div id="puzzle-timer-skeleton" className="puzzle-timer-skeleton" />
        : words.length > 0 && <PuzzleTimer seconds={elapsedSeconds} />
      }
      <span id="game-instructions" className="game-instructions"> Create four groups of four!</span>
      {/* Render solved connections above the grid */}
      <div id="solved-connections-container" className="solved-connections-container">
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
      {/* Grid shows only remaining unsolved words.
          Suppress loading indicator on end screen — the toast handles feedback instead. */}
      <GameGrid words={remainingWords} loading={loading && !showEndScreen} error={error} poolExhausted={poolExhausted} animationPhase={animationPhase} />
      {/* Only render mistake tracker, control buttons, and forfeit until end screen shows */}
      {!showEndScreen && (
        <>
          <MistakeTracker mistakesLeft={mistakesLeft} />
          <ControlButtonBar
            onShuffle={handleShuffle}
            onDeselect={() => { }}
            onSubmit={handleSubmit}
          />
          <ForfeitButton onClick={() => setIsForfeitModalOpen(true)} />
        </>
      )}
      <ForfeitConfirmModal
        isOpen={isForfeitModalOpen}
        onCancel={() => setIsForfeitModalOpen(false)}
        onConfirm={handleForfeitConfirm}
      />
      {/* View Results button appears after end screen is ready */}
      {showEndScreen && (
        <>
          <ViewResultsButton onClick={() => setIsResultsModalOpen(true)} />
          {/* Admin play-test: show Back to Admin + Approve or Reject button */}
          {onReviewComplete && (
            <div id="review-actions" className="review-actions">
              <button
                id="review-back-button"
                className="review-back-button"
                onClick={onReviewComplete}
              >
                ← Back to Admin
              </button>
              {reviewPuzzleId && reviewTab === "rejected" && (
                <button
                  id="review-approve-button"
                  className="review-approve-button"
                  onClick={() => handleReviewAction("approve")}
                  disabled={isReviewActioning}
                >
                  {isReviewActioning ? "..." : "✓ Approve"}
                </button>
              )}
              {reviewPuzzleId && reviewTab === "approved" && (
                <button
                  id="review-reject-button"
                  className="review-reject-button"
                  onClick={() => handleReviewAction("reject")}
                  disabled={isReviewActioning}
                >
                  {isReviewActioning ? "..." : "✗ Reject"}
                </button>
              )}
            </div>
          )}
        </>
      )}
      {/* Results modal with emoji grid and share functionality */}
      {gameResult && (
        <ResultsModal
          isOpen={isResultsModalOpen}
          onClose={() => setIsResultsModalOpen(false)}
          onNextPuzzle={reviewGameId ? undefined : () => { setIsResultsModalOpen(false); startNewGame(); }}
          gameResult={gameResult}
          guessHistory={guessHistory}
          connections={connections as Connection[]}
          puzzleNumber={puzzleNumber || 0}
          completionTimeSeconds={elapsedSeconds}
        />
      )}
    </div>
  );
};

export default ConnectionsGame;