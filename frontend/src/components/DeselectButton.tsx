import React from 'react'; // Import React library for JSX support
import { useSelectedWords } from '../context/SelectedWordsContext';

// Define the props interface for DeselectButton component
interface DeselectButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component DeselectButton using TypeScript and React.FC type
const DeselectButton: React.FC<DeselectButtonProps> = ({ onClick }) => {
  const { selectedWords, clearWords } = useSelectedWords();
  const isReadyToDeselect = selectedWords.length > 0;

  // Render a button element with an onClick event handler
  return (
    <button
      className={`deselect-button ${isReadyToDeselect ? "" : "button-unprimed"} p-3 mx-2`}
      onClick={() => {
        if (isReadyToDeselect) {
          clearWords();
          onClick();
        }
      }}
    >
      Deselect all
    </button>
  );
};

export default DeselectButton; // Export the DeselectButton component for use in other parts of the application
