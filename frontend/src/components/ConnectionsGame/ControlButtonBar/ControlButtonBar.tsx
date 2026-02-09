import React from "react";
import ShuffleButton from "./ShuffleButton";
import DeselectButton from "./DeselectButton";
import SubmitButton from "./SubmitButton";

interface ControlButtonBarProps {
  onShuffle: () => void;
  onDeselect: () => void;
  onSubmit: () => void;
  isVisible?: boolean;  // Control fade-out animation when game ends
}

const ControlButtonBar: React.FC<ControlButtonBarProps> = ({ onShuffle, onDeselect, onSubmit, isVisible = true }) => {
  return (
    <div id="control-button-bar" className={`button-bar ${!isVisible ? 'fade-out' : ''}`}>
      <ShuffleButton onClick={onShuffle} />
      <DeselectButton onClick={onDeselect} />
      <SubmitButton onClick={onSubmit} />
    </div>
  );
};

export default ControlButtonBar;
