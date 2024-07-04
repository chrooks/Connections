import React from "react";
import { useSelectedWords } from "../context/SelectedWordsContext";

interface WordCardProps {
  word: string;
}

const WordCard: React.FC<WordCardProps> = ({ word }) => {
  const { selectedWords, addWord, removeWord } = useSelectedWords();
  const isSelected = selectedWords.includes(word);

  const handleClick = (event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent event bubbling
    if (isSelected) {
      removeWord(word);
    } else {
      addWord(word);
    }
  };

  return (
    <div
      className={`word-card ${isSelected ? "word-card-selected" : ""}`}
      onClick={handleClick}
    >
      {word}
    </div>
  );
};

export default WordCard;
