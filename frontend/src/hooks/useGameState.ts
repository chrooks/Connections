import { useState, useEffect } from "react";
import { BASE_URL, GAME_ID } from "../config/gameConfig";

/**
 * Custom hook to manage the game grid state.
 * Fetches the game grid data from the server and handles loading and error states.
 *
 * @param {Function} setMistakesLeft - A function to update the mistakesLeft state.
 * @returns {Object} An object containing the words array, loading state, error state, connections, and shuffleWords function.
 */
const useGameState = (setMistakesLeft: (mistakesLeft: number) => void) => {
  // State to store the words for the game grid
  const [words, setWords] = useState<string[]>([]);
  // State to indicate if the data is currently being loaded
  const [loading, setLoading] = useState<boolean>(true);
  // State to store any error message that occurs during data fetching
  const [error, setError] = useState<string | null>(null);
  // State to store the connections
  const [connections, setConnections] = useState<any[]>([]);

  useEffect(() => {
    /**
     * Fetches the game grid data from the server.
     * Updates the words state if the fetch is successful.
     * Updates the error state if there is an error during the fetch.
     * Sets the loading state to false once the fetch is complete.
     */
    const fetchGameState = async () => {
      try {
        // Send a POST request to the server to fetch the game grid data
        const response = await fetch(`${BASE_URL}/game-status`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            gameId: GAME_ID,
          }),
        });
        // Parse the JSON response from the server
        const jsonResponse = await response.json();
        const data = jsonResponse.data;
        console.log(data);
        if (response.ok) {
          // If the response is successful, update the words state with the fetched data
          setWords(data.grid);
          // Update the mistakesLeft state with the fetched data
          setMistakesLeft(data.mistakesLeft);
          // Update the connections state with the fetched data
          setConnections(data.connections);
        } else {
          // If the response is not successful, update the error state with the error message
          setError(data.error || "Failed to fetch game grid");
        }
      } catch (err) {
        // If there is an error during the fetch, update the error state with the error message
        setError((err as Error).message);
      } finally {
        // Set the loading state to false once the fetch is complete
        setLoading(false);
      }
    };

    fetchGameState();
  }, [setMistakesLeft]);

  /**
   * Shuffles the words in the game grid.
   * Uses the Fisher-Yates algorithm to randomly shuffle the array of words.
   */
  const shuffleWords = () => {
    setWords((prevWords) => {
      // Create a copy of the previous words array to avoid mutating the state directly
      const shuffledWords = [...prevWords];
      // Iterate over the array from the last element to the second element
      for (let i = shuffledWords.length - 1; i > 0; i--) {
        // Generate a random index from 0 to i
        const j = Math.floor(Math.random() * (i + 1));
        // Swap the elements at indices i and j
        [shuffledWords[i], shuffledWords[j]] = [
          shuffledWords[j],
          shuffledWords[i],
        ];
      }
      // Return the shuffled array to update the state
      return shuffledWords;
    });
  };

  return { words, loading, error, connections, shuffleWords };
};

export default useGameState;