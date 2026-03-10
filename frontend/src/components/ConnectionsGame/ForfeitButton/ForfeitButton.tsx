import React from "react";
import "./ForfeitButton.scss";

interface ForfeitButtonProps {
  onClick: () => void;
}

const ForfeitButton: React.FC<ForfeitButtonProps> = ({ onClick }) => {
  return (
    <button
      id="forfeit-button"
      className="forfeit-button"
      onClick={onClick}
    >
      Give Up
    </button>
  );
};

export default ForfeitButton;
