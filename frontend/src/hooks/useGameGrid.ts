import { useState, useEffect } from "react";

/**
 * Custom hook to manage the game grid state.
 * Fetches the game grid data from the server and handles loading and error states.
 * 
 * @returns {Object} An object containing the words array, loading state, and error state.
 */
const useGameGrid = () => {
  // State to store the words for the game grid
  const [words, setWords] = useState<string[]>([]);
  // State to indicate if the data is currently being loaded
  const [loading, setLoading] = useState<boolean>(true);
  // State to store any error message that occurs during data fetching
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    /**
     * Fetches the game grid data from the server.
     * Updates the words state if the fetch is successful.
     * Updates the error state if there is an error during the fetch.
     * Sets the loading state to false once the fetch is complete.
     */
    const fetchGameGrid = async () => {
      try {
        // Send a GET request to the server to fetch the game grid data
        const response = await fetch("/generate-grid", {
          method: "GET",
        });
        // Parse the JSON response from the server
        const data = await response.json();
        if (response.ok) {
          // If the response is successful, update the words state with the fetched data
          setWords(data.words);
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

    fetchGameGrid();
  }, []);

  return { words, loading, error };
};

export default useGameGrid;
