import React, { useState } from "react";

interface WordCardProps {
  word: string;
}

const WordCard: React.FC<WordCardProps> = ({ word }) => {
  const [isSelected, setIsSelected] = useState(false);

  const toggleSelection = () => {
    setIsSelected(!isSelected);
  };

  return (
    <div
      className={`word-card ${isSelected ? "word-card-selected" : ""}`}
      onClick={toggleSelection}
    >
      {word}
    </div>
  );
};

export default WordCard;
