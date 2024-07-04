import React from 'react'; // Import React library for JSX support
import { useSelectedWords } from '../context/SelectedWordsContext';

// Define the props interface for SubmitButton component
interface SubmitButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component SubmitButton using TypeScript and React.FC type
const SubmitButton: React.FC<SubmitButtonProps> = ({ }) => {
  const { selectedWords, clearWords } = useSelectedWords();
  const isReadyToSubmit = selectedWords.length === 4;

  const handleSubmit = () => {
    if (isReadyToSubmit) {
      console.log('Selected words:', selectedWords);
      clearWords();
      // Add your submit logic here
    }
  };

  return (
    <button className={`submit-button ${isReadyToSubmit ? "" : "button-unprimed"} p-3 mx-2`} onClick={handleSubmit}>
      Submit
    </button>
  );
};

export default SubmitButton; // Export the ShuffleButton component for use in other parts of the application
