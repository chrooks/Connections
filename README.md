# Connections

The Connections Game is a web application inspired by the NY Times game, offering players a challenging and engaging way to test their ability to identify connections between words. Built with Flask and React, this game challenges players to select sets of words that share a common theme from a grid. Success reveals interesting connections and further enriches the gameplay experience.

## Features

- **Dynamic Word Grids**: Every game generates a unique set of words and connections, ensuring a fresh challenge for players every time.
- **Game State Management**: Players have a limited number of guesses to find all connections, with the game tracking and displaying remaining guesses.
- **Responsive Design**: A user-friendly interface that adjusts to various screen sizes for an optimal playing experience.

## Getting Started

### Prerequisites

- Python 3.6+
- Node.js and npm
- Flask
- React

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/chrooks/Connections.git
cd Connections
```

2. **Set up the Python virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r backend/requirements.txt
```

3. **Start the Flask backend**

```bash
cd backend
export FLASK_APP=app.py  # On Windows use `set FLASK_APP=app.py`
export FLASK_ENV=development  # On Windows use `set FLASK_ENV=development`
flask run
```

4. **Install and run the React frontend**

```bash
cd ../frontend
npm install
npm start
```

Your application should now be running on `localhost:3000` (frontend) and the Flask backend on `localhost:5000`.

### Playing the Game

- Navigate to `http://localhost:3000` in your web browser to start playing.
- Press the "Play" button to generate a new grid of words.
- Select four words that you believe are connected and submit your guess.
- If correct, the words will be removed and their connection revealed. If incorrect, try again until you find all connections or run out of guesses.

## Technical Details

### Technology Stack

- **Frontend**:

  - **Vite**: Used for bootstrapping the frontend, offering a fast and efficient development experience with React.
  - **React**: Powers the dynamic user interface, making the game interactive and responsive.
  - **TypeScript**: Provides strong typing for React components and utilities, enhancing code quality and maintainability.

- **Backend**:

  - **Flask**: A lightweight Python framework used for backend logic and API endpoints, facilitating the game's core functionalities.
  - **Python**: The primary programming language for backend development, chosen for its simplicity and effectiveness.

- **Word and Connection Generation**:
  - **LLM**: Utilized to dynamically generate the words that compose the game's grid and their relationships, ensuring a unique and challenging experience every game.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any improvements or bug fixes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
