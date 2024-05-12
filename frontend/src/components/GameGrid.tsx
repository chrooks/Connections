import React from "react";
import WordCard from "./WordCard";

interface GameGridProps {
  // Define the props for the GameGrid component
  // e.g., words: string[], onWordSelected: (word: string) => void, etc.
}

const GameGrid: React.FC<GameGridProps> = (props) => {
  // Logic for rendering the grid of WordCard components based on the game data
  // You can use a loop or map function to generate the WordCard components

  return (
    <div className="game-grid">
      {/* Render the WordCard components */}
      {/* Example: */}
      {/* {props.words.map((word, index) => (
        <WordCard key={index} word={word} onSelected={() => props.onWordSelected(word)} />
      ))} */}
      <WordCard word="test" />
      <WordCard word="test" />
      <WordCard word="test" />
      <WordCard word="test" />
    </div>
  );
};

export default GameGrid;
