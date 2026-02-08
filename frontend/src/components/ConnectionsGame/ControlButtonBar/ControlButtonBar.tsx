import React from "react";
import ShuffleButton from "./ShuffleButton";
import DeselectButton from "./DeselectButton";
import SubmitButton from "./SubmitButton";

interface ControlButtonBarProps {
  onShuffle: () => void;
  onDeselect: () => void;
  onSubmit: () => void;
}

const ControlButtonBar: React.FC<ControlButtonBarProps> = (props) => {
  return (
    <div id="control-button-bar" className="button-bar">
      <ShuffleButton onClick={props.onShuffle} />
      <DeselectButton onClick={props.onDeselect} />
      <SubmitButton onClick={props.onSubmit} />
    </div>
  );
};

export default ControlButtonBar;
