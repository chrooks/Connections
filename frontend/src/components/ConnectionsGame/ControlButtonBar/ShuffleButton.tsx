import React from 'react'; // Import React library for JSX support

// Define the props interface for ShuffleButton component
interface ShuffleButtonProps {
  onClick: () => void; // Type definition for the onClick event handler function
}

// Functional component ShuffleButton using TypeScript and React.FC type
const ShuffleButton: React.FC<ShuffleButtonProps> = ({ onClick }) => {
  // Render a button element with an onClick event handler
  return (
    <button id="shuffle-button" className="shuffle-button" onClick={onClick}>
      Shuffle
    </button>
  );
};

export default ShuffleButton; // Export the ShuffleButton component for use in other parts of the application


