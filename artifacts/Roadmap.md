# Roadmap

## Project Breakdown

**Frontend:**

- **Technology:** React.js
- **Main Features:**
  - Navigation to the game page and a play button.
  - A 4x4 grid display for the game tiles with words.
  - Interaction for selecting tiles and submitting guesses.
  - Feedback mechanism for correct/incorrect guesses.
  - Display for remaining guesses and game over condition.

**Backend:**

- **Technology:** Flask
- **Main Features:**
  - API to generate game tiles with words and connections (using your GPT prompt).
  - Mechanism to validate player guesses and manage game state (correct guesses, incorrect guesses, and game over logic).
  - Database interaction for storing game states or user progress (if needed for future features like leaderboards or user accounts).

### Step-by-Step Implementation Guide

**Step 1: Setup Your Project Environment**

- Initialize a new React app (using Create React App for simplicity).
- Set up a Python backend using Flask or Django (Flask for simplicity, Django for more built-in features).

**Step 2: Design Your Game Logic and Data Structure**

- Define the data structure for your game grid, player guesses, and validations.
- Implement the game logic on the backend to handle the generation of words, connections, and validation of guesses.

**Step 3: Develop the Frontend**

- Implement the game interface in React with components for the game grid, play button, submit guess button, and feedback displays.
- Use state management (React's useState or useReducer hooks) to handle game states on the frontend.

**Step 4: Backend API Development**

- Develop an API endpoint to generate the game grid based on the GPT prompt.
- Create API endpoints to handle guesses, validate them, and manage game state (number of incorrect guesses, game over condition).

**Step 5: Integrating Frontend with Backend**

- Use React to fetch from your backend API to populate the game grid.
- Handle user interactions (tile selections, guess submissions) and communicate with the backend for validation and game state updates.

**Step 6: Testing and Debugging**

- Test the game thoroughly to ensure all interactions work as expected and debug any issues.

**Step 7: Deployment**

- Deploy your React application and Python backend to a web server or cloud service (like Heroku, AWS, or Vercel for the frontend).

### Additional Suggestions

- **User Experience:** Consider adding animations or visual cues for feedback on correct/incorrect guesses.
- **Scalability:** If planning for multiplayer or high user volume, ensure your backend is scalable.
- **Security:** Implement security best practices, especially if you plan to add user accounts or handle sensitive data.

# Current Progress

Your Flask application is designed to support a game where players guess connections between words. Here's a summary of its functionality and structure:

Game State Storage: Utilizes an in-memory dictionary (games) to store game states. Each game state includes the game grid, relationships between words, remaining guesses, and a flag to indicate if the game is over. This is a temporary solution, and a database is recommended for production use.

Mock GPT API Call: Implements call_gpt_api(prompt), a mock function returning a fixed set of words and their categories to simulate generating word grids and their connections via a GPT model.

Game Grid Generation: generate_game_grid() reads a prompt from backend/prompt.txt, simulates a call to the GPT API, and parses the response to create a game grid and map words to their relationships. It handles file not found and other exceptions, shuffles the grid for randomness, and ensures no leading or trailing whitespace in words or relationships.

Request Parsing and Validation: parse_and_validate_request(required_fields) checks if the necessary fields are present in the request's JSON payload, returning the data and any errors encountered.

Endpoints:

/generate-grid (POST): Creates a new game session with a unique game ID and a generated word grid. It handles errors in grid generation gracefully.
/submit-guess (POST): Processes player guesses, updating the game state based on the correctness of the guess. It needs further implementation for validating guesses against the relationships.
/game-status (GET): Returns the current status of a game, including the grid, remaining guesses, and whether the game is over, based on a provided game ID.
/restart-game (POST): Restarts a game with the same game ID, resetting the grid and guesses. It requires further implementation for generating a new grid.
Error Handling: The application handles potential errors, such as missing prompt.txt, invalid game IDs, and incomplete request payloads, providing appropriate feedback to the client.

Future Work: The application requires further development for dynamic word grid generation via actual GPT API calls, implementation of guess validation logic, and transitioning from in-memory storage to a database for persistence.

This structure sets a solid foundation for a word-connection game, with placeholders and TODOs indicating areas needing further development or integration with external APIs and databases for full functionality.



# Notes:

Selected words stay selected after shuffling
Words fade in after shuffling
Selections persist between sessions -> which words have been selected to guess is also stored in the backend
Once you've selected 4 words -> Submit button turns black
After pressing Submit
- the 4 selected word boxes jump from top left to bottom right
- the Submit button turns back to grey
- If incorrect, a mistake indicator shrinks