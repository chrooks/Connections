import { useState, useEffect } from "react";
import { apiPost, apiGet } from "../lib/api";

// Store current game ID in memory (persists across hook calls but not page refreshes)
let currentGameId: string | null = null;

/**
 * Custom hook to manage the game grid state.
 * Fetches the game grid data from the server and handles loading and error states.
 * Automatically creates a new game if none exists.
 *
 * @param {Function} setMistakesLeft - A function to update the mistakesLeft state.
 * @returns {Object} An object containing the words array, loading state, error state, connections, gameId, and shuffleWords function.
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
  // State to store the current game ID
  const [gameId, setGameId] = useState<string | null>(currentGameId);

  useEffect(() => {
    /**
     * Creates a new game and returns the game ID.
     */
    const createNewGame = async (): Promise<string | null> => {
      try {
        const response = await apiGet("/generate-grid");
        const jsonResponse = await response.json();
        if (response.ok && jsonResponse.data?.gameId) {
          return jsonResponse.data.gameId;
        }
        return null;
      } catch {
        return null;
      }
    };

    /**
     * Fetches the game state for the given game ID.
     */
    const fetchGameState = async (id: string) => {
      const response = await apiPost("/game-status", { gameId: id });
      const jsonResponse = await response.json();

      if (response.ok && jsonResponse.data) {
        const data = jsonResponse.data;
        setWords(data.grid);
        setMistakesLeft(data.mistakesLeft);
        setConnections(data.connections);
        return true;
      }
      return false;
    };

    /**
     * Main initialization: try existing game or create new one.
     */
    const initializeGame = async () => {
      try {
        // If we have a stored game ID, try to fetch it
        if (currentGameId) {
          const success = await fetchGameState(currentGameId);
          if (success) {
            setGameId(currentGameId);
            setLoading(false);
            return;
          }
        }

        // No valid game exists, create a new one
        const newGameId = await createNewGame();
        if (newGameId) {
          currentGameId = newGameId;
          setGameId(newGameId);
          await fetchGameState(newGameId);
        } else {
          setError("Failed to create a new game");
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    initializeGame();
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

  return { words, loading, error, connections, shuffleWords, gameId };
};

export default useGameState;