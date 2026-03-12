/**
 * GameHistoryModal shows the full result for a single past game.
 *
 * Displays all four connection groups (colour-coded like the live game),
 * an emoji guess grid identical to the results screen, and a copy button.
 * Connections the player never solved are shown greyed-out with a dashed border.
 */

import React, { useMemo } from "react";
import Modal from "react-modal";
import { toast } from "react-toastify";
import { GameHistoryEntry } from "../../types/profile";
import "./GameHistoryModal.scss";

// NYT-style difficulty colours — same order used by SolvedConnection
const DIFFICULTY_COLORS = ["#f9df6d", "#a0c35a", "#b0c4ef", "#ba81c5"];
const EMOJI_MAP = ["🟨", "🟩", "🟦", "🟪"];

interface GameHistoryModalProps {
  entry: GameHistoryEntry | null;
  onClose: () => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const GameHistoryModal: React.FC<GameHistoryModalProps> = ({ entry, onClose }) => {
  // Build the emoji grid from guess history — same algorithm as ResultsModal
  const emojiGrid = useMemo(() => {
    if (!entry) return "";
    return entry.previousGuesses
      .map((guess) =>
        guess
          .map((word) => {
            const idx = entry.connections.findIndex((c) => c.words.includes(word));
            return EMOJI_MAP[idx] ?? "⬜";
          })
          .join("")
      )
      .join("\n");
  }, [entry]);

  const shareText = useMemo(() => {
    if (!entry) return "";
    const label =
      entry.puzzleNumber !== null ? `Puzzle #${entry.puzzleNumber}` : "Practice";
    return `Connections\n${label}\n${emojiGrid}`;
  }, [entry, emojiGrid]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      toast.success("Copied results to clipboard", {
        position: "top-center",
        autoClose: 2000,
        hideProgressBar: true,
      });
    } catch {
      toast.error("Failed to copy to clipboard", {
        position: "top-center",
        autoClose: 2000,
      });
    }
  };

  return (
    <Modal
      isOpen={entry !== null}
      onRequestClose={onClose}
      className="game-history-modal"
      overlayClassName="game-history-modal-overlay"
      contentLabel="Game result"
      ariaHideApp={false}
      shouldCloseOnOverlayClick={true}
    >
      {entry && (
        <div id="game-history-modal-content" className="game-history-modal-content">
          {/* Header: puzzle label + outcome badge + close button */}
          <div id="game-history-modal-header" className="game-history-modal-header">
            <div className="game-history-modal-title">
              <span id="game-history-modal-puzzle" className="game-history-modal-puzzle">
                {entry.puzzleNumber !== null
                  ? `Puzzle #${entry.puzzleNumber}`
                  : "Practice"}
                {entry.puzzleModifiedSincePlayed && (
                  <span
                    id={`game-history-modal-modified-badge-${entry.gameId}`}
                    className="history-modified-badge"
                    title="This puzzle was edited after you played it"
                  >
                    {" "}⚠
                  </span>
                )}
              </span>
              <span
                id="game-history-modal-outcome"
                className={`game-history-modal-outcome outcome-${entry.outcome.toLowerCase()}`}
              >
                {entry.outcome}
              </span>
            </div>
            <button
              id="game-history-modal-close"
              className="game-history-modal-close"
              onClick={onClose}
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* Completion time */}
          {entry.completionTimeSeconds !== null && (
            <p id="game-history-modal-time" className="game-history-modal-time">
              ⏱ {formatTime(entry.completionTimeSeconds)}
            </p>
          )}

          {/* All four connection groups — solved ones get their colour, unsolved get grey */}
          <div id="game-history-connections" className="game-history-connections">
            {entry.connections.map((conn, i) => (
              <div
                key={i}
                id={`game-history-connection-${i}`}
                className={`game-history-connection${!conn.guessed ? " game-history-connection--unsolved" : ""}`}
                style={conn.guessed ? { backgroundColor: DIFFICULTY_COLORS[i] } : undefined}
              >
                <span className="game-history-connection-category">
                  {conn.relationship}
                </span>
                <span className="game-history-connection-words">
                  {conn.words.join(", ")}
                </span>
              </div>
            ))}
          </div>

          {/* Emoji guess grid */}
          {entry.previousGuesses.length > 0 && (
            <div id="game-history-emoji-grid" className="game-history-emoji-grid">
              {emojiGrid}
            </div>
          )}

          {/* Copy button */}
          <button
            id="game-history-copy-button"
            className="game-history-copy-button"
            onClick={handleCopy}
          >
            Copy Results
          </button>
        </div>
      )}
    </Modal>
  );
};

export default GameHistoryModal;
