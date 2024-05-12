import React from "react";
import Navbar from "./components/navbar/Navbar";
import Game from "./components/Game";

const App: React.FC = () => {
  return (
    <div className="app">
      <Navbar />
      <Game />
    </div>
  );
};

export default App;
