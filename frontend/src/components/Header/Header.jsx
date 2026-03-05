import { Link } from 'react-router-dom';
import { SquarePlay, CircleUserRound } from 'lucide-react';
import './Header.css'; 

export function Header() {
  return (
    <header className="header">
       <Link to="/" className="brand">
           SMARTSCOUT
       </Link> 

       <div className="actionsGroup">
           <button 
             className="iconButton " 
             aria-label="Iniciar Análise"
             title="Iniciar Análise"
           >
               <SquarePlay size={32} />
           </button>
           
           <button 
             className="iconButton " 
             aria-label="Perfil do Usuário"
             title="Perfil"
           >
               <CircleUserRound size={32} />
           </button>
       </div>
    </header>
  );
}