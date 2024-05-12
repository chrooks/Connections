import React from "react";
import GameGrid from "./GameGrid";
import MistakeTracker from "./MistakeTracker";
import ButtonBar from "./ButtonBar";

const Game: React.FC = () => {
  // Game state and logic will be managed here

  return (
    <div className="game container d-flex flex-column align-items-center justify-content-center">
      <span className="game-instructions"> Create four groups of four!</span>
      <div className="game-grid-container">
        <GameGrid />
      </div>
      <div className="game-mistake-tracker">
        <MistakeTracker />
      </div>
      <div className="game-button-bar">
        <ButtonBar />
      </div>
    </div>
  );
};

export default Game;
