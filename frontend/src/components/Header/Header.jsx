import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  SquarePlay,
  CircleUserRound,
  X,
  Mail,
  BadgeCheck
} from 'lucide-react';
import './Header.css';

export function Header() {
  const [showProfileModal, setShowProfileModal] = useState(false);
  const navigate = useNavigate();

  // Exemplo de dados do usuário
  const user = {
    name: 'Pedro Ponte Negra',
    email: 'Pedro@smartscout.com',
    role: 'Analista Chefe do Setor'
  };

  function handleOpenProfileModal() {
    setShowProfileModal(true);
  }

  function handleCloseProfileModal() {
    setShowProfileModal(false);
  }

  function handleLogout() {
    // Exemplo de logout:
    localStorage.removeItem('token');
    localStorage.removeItem('user');

    setShowProfileModal(false);
    navigate('/login');
  }

  useEffect(() => {
    function handleEsc(event) {
      if (event.key === 'Escape') {
        setShowProfileModal(false);
      }
    }

    if (showProfileModal) {
      window.addEventListener('keydown', handleEsc);
    }

    return () => {
      window.removeEventListener('keydown', handleEsc);
    };
  }, [showProfileModal]);

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          SMARTSCOUT
        </Link>

        <div className="actionsGroup">
          <button
            className="iconButton"
            aria-label="Iniciar Análise"
            title="Iniciar Análise"
          >
            <SquarePlay size={32} />
          </button>

          <button
            className="iconButton"
            aria-label="Perfil do Usuário"
            title="Perfil"
            onClick={handleOpenProfileModal}
          >
            <CircleUserRound size={32} />
          </button>
        </div>
      </header>

      {showProfileModal && (
        <div className="profileOverlay" onClick={handleCloseProfileModal}>
          <div
            className="profileModal"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="closeModalButton"
              onClick={handleCloseProfileModal}
              aria-label="Fechar modal"
            >
              <X size={20} />
            </button>

            <div className="profileTop">
              <div className="profileAvatar">
                {user.name.charAt(0).toUpperCase()}
              </div>

              <h2 className="profileName">{user.name}</h2>
              <p className="profileSubtitle">Informações da conta</p>
            </div>

            <div className="profileInfoCard">
              <div className="profileInfoRow">
                <Mail size={18} />
                <div>
                  <span className="infoLabel">E-mail</span>
                  <strong>{user.email}</strong>
                </div>
              </div>

              <div className="profileInfoRow">
                <BadgeCheck size={18} />
                <div>
                  <span className="infoLabel">Perfil</span>
                  <strong>{user.role}</strong>
                </div>
              </div>
            </div>

            <div className="profileActions">
              <button className="logoutButton" onClick={handleLogout}>
                Sair da conta
              </button>

              <button
                className="secondaryButton"
                onClick={handleCloseProfileModal}
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}