import React from "react";
import "./PuzzleTimer.scss";

interface PuzzleTimerProps {
  seconds: number;
}

/**
 * Displays elapsed game time in MM:SS format above the game instructions.
 * Receives the current second count from ConnectionsGame.
 */
const PuzzleTimer: React.FC<PuzzleTimerProps> = ({ seconds }) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  const formatted = hours > 0
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;

  return (
    <div id="puzzle-timer" className="puzzle-timer">
      {formatted}
    </div>
  );
};

export default PuzzleTimer;
