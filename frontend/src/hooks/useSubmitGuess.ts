import { useState } from "react";
import { toast } from "react-toastify";
import 'react-toastify/dist/ReactToastify.css';
import { BASE_URL } from "../config/gameConfig";

// Result returned from submitGuess for animation chaining
export interface SubmitGuessResult {
  isCorrect: boolean;
  isNewGuess: boolean;
  guessedConnections: boolean[];
}

/**
 * Custom hook to handle the submission of guesses.
 * Manages loading and error states during the submission process.
 * Returns result data so animations can be chained before state updates.
 *
 * @param {Function} setMistakesLeft - Callback to update mistakes remaining
 * @returns {Object} An object containing the submitGuess function, loading state, and error state.
 */
const useSubmitGuess = (
  setMistakesLeft: (mistakesLeft: number) => void
) => {
  // State to indicate if the guess submission is currently in progress
  const [loading, setLoading] = useState(false);
  // State to store any error message that occurs during guess submission
  const [error, setError] = useState<string | null>(null);

  /**
   * Submits the selected words as a guess to the server.
   * Returns the result so animations can be chained before updating state.
   *
   * @param {string} gameId - The ID of the game.
   * @param {string[]} selectedWords - The selected words to be submitted as a guess.
   * @returns {Promise<SubmitGuessResult | null>} Result data or null if error
   */
  const submitGuess = async (gameId: string, selectedWords: string[]): Promise<SubmitGuessResult | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${BASE_URL}/submit-guess`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ gameId: gameId, guess: selectedWords }),
      });

      const result = await response.json();

      if (result.error) {
        console.error(result.error);
        setError(result.error);
        toast.error(result.error);
        return null;
      } else if (result.data) {
        const responseData = result.data;
        console.log("Response Data: ", responseData);

        // Update mistakes immediately
        setMistakesLeft(responseData.gameState.mistakesLeft);

        // Show toasts for non-correct guesses
        if (!responseData.isNewGuess) {
          toast.warn("Already guessed!", {
            theme: "dark",
            icon: false,
            hideProgressBar: true,
          });
        } else if (!responseData.isCorrect) {
          console.log("Guess is incorrect");
          toast.error("Guess is incorrect!");
        }

        // Return result for animation chaining
        return {
          isCorrect: responseData.isCorrect,
          isNewGuess: responseData.isNewGuess,
          guessedConnections: responseData.gameState.guessedConnections,
        };
      }
      return null;
    } catch (err) {
      console.error("An error occurred:", err);
      setError("An error occurred while submitting the guess.");
      toast.error("An error occurred while submitting the guess.", {
        icon: false,
      });
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { submitGuess, loading, error };
};

export default useSubmitGuess;