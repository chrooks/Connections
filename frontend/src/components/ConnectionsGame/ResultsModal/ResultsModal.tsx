import React, { useMemo } from "react";
import Modal from "react-modal";
import { toast } from "react-toastify";
import { useAuth } from "../../../context/AuthContext";
import "./ResultsModal.scss";

// Type for a connection object from the API
interface Connection {
  relationship: string;
  words: string[];
  guessed: boolean;
}

// Type for tracking guess history
interface GuessHistoryEntry {
  guess: string[];
  isCorrect: boolean;
  connectionIndex: number | null;
}

interface ResultsModalProps {
  isOpen: boolean;
  onClose: () => void;
  gameResult: 'WIN' | 'LOSS';
  guessHistory: GuessHistoryEntry[];
  connections: Connection[];
  puzzleNumber: number;
}

/**
 * Modal displaying game results with shareable emoji grid.
 * Shows performance title, guess visualization, and share functionality.
 */
const ResultsModal: React.FC<ResultsModalProps> = ({
  isOpen,
  onClose,
  gameResult,
  guessHistory,
  connections,
  puzzleNumber
}) => {
  const { user } = useAuth();

  // Determine result title based on performance
  const resultTitle = useMemo(() => {
    if (gameResult === 'LOSS') return 'Next time!';
    const totalGuesses = guessHistory.length;
    if (totalGuesses === 4) return 'Perfect!';
    if (totalGuesses <= 6) return 'Solid!';
    return 'Great!';
  }, [gameResult, guessHistory.length]);

  // Generate emoji grid from guess history
  const emojiGrid = useMemo(() => {
    const emojiMap = ['🟨', '🟩', '🟦', '🟪'];

    return guessHistory.map(entry => {
      // For each word in the guess, find which connection it belongs to and show that emoji
      return entry.guess.map(word => {
        const connIdx = connections.findIndex(conn => conn.words.includes(word));
        return emojiMap[connIdx] || '⬜'; // Fallback to white square if not found
      }).join('');
    }).join('\n');
  }, [guessHistory, connections]);

  // Generate share text in Connections format
  const shareText = useMemo(() => {
    return `Connections\nPuzzle #${puzzleNumber}\n${emojiGrid}`;
  }, [puzzleNumber, emojiGrid]);

  // Handle share button click - copy to clipboard
  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      toast.success('Copied results to clipboard', {
        position: "top-center",
        autoClose: 2000,
        hideProgressBar: true,
        closeOnClick: true,
        pauseOnHover: true,
      });
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      toast.error('Failed to copy to clipboard', {
        position: "top-center",
        autoClose: 2000,
      });
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onRequestClose={onClose}
      className="results-modal"
      overlayClassName="results-modal-overlay"
      contentLabel="Game Results"
      ariaHideApp={false}
      shouldCloseOnOverlayClick={false}
    >
      <div className="results-modal-content">
        {/* Close button */}
        <button
          id="results-modal-close"
          className="results-close-button"
          onClick={onClose}
        >
          ✕ Back to puzzle
        </button>

        {/* Result title based on performance */}
        <h1 className="results-title">{resultTitle}</h1>

        {/* Subtitle */}
        <p className="results-subtitle">
          Track your Connections streaks and earn badges for big achievements.
        </p>

        {/* Create account button for guest users */}
        {!user && (
          <button
            id="results-create-account-button"
            className="create-account-button"
            onClick={() => {
              // TODO: Open auth modal - will need to pass this handler from parent
              console.log('Open auth modal');
            }}
          >
            Create a free account
          </button>
        )}

        {/* Emoji grid visualization */}
        <div id="results-emoji-grid" className="emoji-grid">
          {emojiGrid}
        </div>

        {/* Share button */}
        <button
          id="results-share-button"
          className="share-button"
          onClick={handleShare}
        >
          Share Your Results
        </button>
      </div>
    </Modal>
  );
};

export default ResultsModal;
