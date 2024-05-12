import React from 'react'; // Import React library for JSX support
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faRemove } from '@fortawesome/free-solid-svg-icons';

// Define the props interface for DeselectButton component
interface DeselectButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component DeselectButton using TypeScript and React.FC type
const DeselectButton: React.FC<DeselectButtonProps> = ({ onClick }) => {
  // Render a button element with an onClick event handler
  return (
    <button className="deselect-button  mx-2" onClick={onClick}>
      <FontAwesomeIcon icon={faRemove} />
    </button>
  );
};

export default DeselectButton; // Export the DeselectButton component for use in other parts of the application
