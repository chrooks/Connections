import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './components/App/App'
import 'bootstrap/dist/css/bootstrap.min.css';
import "../styles/main.scss";

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
