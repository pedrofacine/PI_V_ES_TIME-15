import "./SignUp.css"
import logo from "../../assets/logo.png"
import { useState } from "react"

export default function SignUp({ onLoginClick }) {
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")

  const handleSignUp = (e) => {
    e.preventDefault()
    // Lógica de registro aqui
    console.log("SignUp:", firstName, lastName, email, password)
  }

  return (
    <div className="signup-page bg-gradient">
      <div className="signup-card">

        <img src={logo} className="signup-logo" alt="SmartScout" />

        <h2 className="signup-title">Registe-se</h2>

        <form className="signup-form" onSubmit={handleSignUp}>

          <div className="signup-row">
            <div className="input-group">
              <label className="input-label">Nome</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  placeholder=""
                  className="input-base"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </div>
            </div>

            <div className="input-group">
              <label className="input-label">Sobrenome</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  placeholder=""
                  className="input-base"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">E-mail</label>
            <div className="input-wrapper">
              <input
                type="email"
                placeholder="seu-email@email.com"
                className="input-base"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="signup-row">
            <div className="input-group">
              <label className="input-label">Senha</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  placeholder=""
                  className="input-base"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div className="input-group">
              <label className="input-label">Confirmar Senha</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  placeholder=""
                  className="input-base"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="password-requirements">
            <ul>
              <li>Mínimo de 8 caracteres</li>
              <li>Inclua ao menos uma letra</li>
            </ul>
          </div>

          <button type="submit" className="btn btn-primary signup-button">
            Registrar
          </button>

          <p className="have-account">
            Já possui conta? <a href="#" onClick={(e) => { e.preventDefault(); onLoginClick(); }} className="login-link">Entrar</a>
          </p>

        </form>

      </div>
    </div>
  )
}
