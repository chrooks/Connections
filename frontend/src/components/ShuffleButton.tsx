import React from 'react'; // Import React library for JSX support
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faShuffle } from '@fortawesome/free-solid-svg-icons';

// Define the props interface for ShuffleButton component
interface ShuffleButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component ShuffleButton using TypeScript and React.FC type
const ShuffleButton: React.FC<ShuffleButtonProps> = ({ onClick }) => {
  // Render a button element with an onClick event handler
  return (
    <button className="shuffle-button mx-2" onClick={onClick}>
      <FontAwesomeIcon icon={faShuffle} />
    </button>
  );
};

export default ShuffleButton; // Export the ShuffleButton component for use in other parts of the application
