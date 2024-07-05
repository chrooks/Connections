import React, { useState } from "react";
import Modal from "react-modal";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGear } from '@fortawesome/free-solid-svg-icons';

const SettingsButton: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleSettingsClick = () => {
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
  };

  return (
    <>
      <button onClick={handleSettingsClick} className="settings-button">
        <FontAwesomeIcon icon={faGear} size="lg" />
      </button>
      <Modal
        isOpen={isModalOpen}
        onRequestClose={closeModal}
        contentLabel="Settings Modal"
        className="modal"
        overlayClassName="modal-overlay"
      >
        <div className="modal-content">
          <span className="close-button" onClick={closeModal}>&times;</span>
          <h2>Settings</h2>
          <p>Settings content goes here...</p>
        </div>
      </Modal>
    </>
  );
};

export default SettingsButton;
