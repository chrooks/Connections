import React from 'react'; // Import React library for JSX support
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPaperPlane } from '@fortawesome/free-solid-svg-icons';

// Define the props interface for SubmitButton component
interface SubmitButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component SubmitButton using TypeScript and React.FC type
const SubmitButton: React.FC<SubmitButtonProps> = ({ onClick }) => {
  // Render a button element with an onClick event handler
  return (
    <button className="submit-button mx-2" onClick={onClick}>
      <FontAwesomeIcon icon={faPaperPlane} />
    </button>
  );
};

export default SubmitButton; // Export the ShuffleButton component for use in other parts of the application
