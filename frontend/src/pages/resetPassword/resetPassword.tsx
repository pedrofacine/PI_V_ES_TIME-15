import "./resetPassword.css"
import logo from "../../assets/logo.png"
import { SyntheticEvent, useState } from "react"
import { Mail } from "lucide-react"
import { Link } from "react-router-dom"

export default function resetPassword() {
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState("")

  const handleResetPassword = (e: SyntheticEvent) => {
    e.preventDefault()

    console.log("Enviar instruções para:", email)
    setMessage("Instruções enviadas para o seu e-mail!")
  }

  return (
    <div className="reset-password-page bg-gradient">
      <div className="white-container">
        
        <img src={logo} className="reset-password-logo" alt="SmartScout" />

        <h2 className="reset-password-title">Redefinir Senha</h2>
        <p className="reset-password-subtitle">
            Insira o e-mail associado à sua conta e enviaremos instruções para redefinir sua senha.
        </p>

        <form className="reset-password-form" onSubmit={handleResetPassword}>
          
          <div className="input-group">
            <label className="input-label">E-mail</label>
            <div className="input-wrapper">
              <span className="input-icon"><Mail/></span>
              <input
                type="email"
                className="input-base with-icon"
                placeholder="seu-email@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          {message && <p className="success-message">{message}</p>}

          <button
            type="submit"
            className="btn btn-primary reset-password-button"
          >
            Prosseguir
          </button>

          <p className="back-to-login">
            <Link to="/login" className="login-link">
              Voltar para o Login
            </Link>
          </p>

        </form>
      </div>
    </div>
  )
}