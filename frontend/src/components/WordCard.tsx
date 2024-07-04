import React from "react";

interface WordCardProps {
  word: string;
  onSelected: () => void;
}

const WordCard: React.FC<WordCardProps> = ({ word, onSelected }) => {
  return (
    <div onClick={onSelected}>
      {word}
    </div>
  );
};

export default WordCard;
