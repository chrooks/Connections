import React from "react";
import Modal from "react-modal";
import "./ForfeitConfirmModal.scss";

interface ForfeitConfirmModalProps {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Confirmation dialog before forfeiting the puzzle.
 * Deliberately styled low-key so it doesn't feel like the game ending yet.
 */
const ForfeitConfirmModal: React.FC<ForfeitConfirmModalProps> = ({
  isOpen,
  onCancel,
  onConfirm,
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onRequestClose={onCancel}
      className="forfeit-confirm-modal"
      overlayClassName="forfeit-confirm-overlay"
      contentLabel="Confirm forfeit"
      ariaHideApp={false}
    >
      <div id="forfeit-confirm-content" className="forfeit-confirm-content">
        <h2 id="forfeit-confirm-title" className="forfeit-confirm-title">
          Give up?
        </h2>
        <p id="forfeit-confirm-body" className="forfeit-confirm-body">
          The answers will be revealed. This counts as a loss.
        </p>
        <div id="forfeit-confirm-actions" className="forfeit-confirm-actions">
          <button
            id="forfeit-cancel-button"
            className="forfeit-cancel-button"
            onClick={onCancel}
          >
            Keep playing
          </button>
          <button
            id="forfeit-confirm-button"
            className="forfeit-confirm-button"
            onClick={onConfirm}
          >
            Yes, give up
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default ForfeitConfirmModal;
