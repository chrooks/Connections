import React, { createContext, useState, useContext, ReactNode } from 'react';

// Define the shape of the context state
interface SelectedWordsContextType {
  selectedWords: string[]; // Array of selected words
  addWord: (word: string) => void; // Function to add a word to the selected words
  removeWord: (word: string) => void; // Function to remove a word from the selected words
  clearWords: () => void; // Function to clear all selected words
}

// Create the context with a default value
const SelectedWordsContext = createContext<SelectedWordsContextType | undefined>(undefined);

// Create a provider component
export const SelectedWordsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedWords, setSelectedWords] = useState<string[]>([]); // State to hold the selected words
  const MAX_SELECTIONS = 4; // Maximum number of words that can be selected

  // Function to add a word to the selected words
  const addWord = (word: string) => {
    if (selectedWords.length < MAX_SELECTIONS) {
      console.log('Adding word', word);
      setSelectedWords((prevWords) => [...prevWords, word]);
    }
  };

  // Function to remove a word from the selected words
  const removeWord = (word: string) => {
    console.log('Removing word', word);
    setSelectedWords((prevWords) => prevWords.filter((w) => w !== word));
  };

  // Function to clear all selected words
  const clearWords = () => {
    console.log('Clearing selected words');
    setSelectedWords([]);
  };

  return (
    // Provide the selected words and functions to the context
    <SelectedWordsContext.Provider value={{ selectedWords, addWord, removeWord, clearWords }}>
      {children}
    </SelectedWordsContext.Provider>
  );
};

// Custom hook to use the SelectedWordsContext
export const useSelectedWords = () => {
  const context = useContext(SelectedWordsContext); // Get the context value
  if (!context) {
    throw new Error('useSelectedWords must be used within a SelectedWordsProvider'); // Throw an error if the hook is used outside the provider
  }
  return context; // Return the context value
};
