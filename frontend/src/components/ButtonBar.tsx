import React from "react";
import ShuffleButton from "./ShuffleButton";
import DeselectButton from "./DeselectButton";
import SubmitButton from "./SubmitButton";

interface ButtonBarProps {
  onShuffle: () => void;
  onDeselect: () => void;
  onSubmit: () => void;
}

const ButtonBar: React.FC<ButtonBarProps> = (props) => {
  return (
    <div className="button-bar">
      <ShuffleButton onClick={props.onShuffle} />
      <DeselectButton onClick={props.onDeselect} />
      <SubmitButton onClick={props.onSubmit} />
    </div>
  );
};

export default ButtonBar;
