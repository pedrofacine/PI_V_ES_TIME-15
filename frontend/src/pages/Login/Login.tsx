import "./Login.css"
import logo from "../../assets/logo.png"
import { SyntheticEvent, useState } from "react"
import { Lock, Mail } from "lucide-react"
import { Link } from "react-router-dom"

export default function Login() {

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleLogin = (e: SyntheticEvent) => {
    e.preventDefault()

    if (!email || !password) {
      setError("Preencha e-mail e senha.")
      return
    }

    setError("")
    console.log("Login:", email, password)

    // aqui depois entra a lógica de login
  }

  return (
    <div className="login-page bg-gradient">
      <div className="white-container">

        <img src={logo} className="login-logo" alt="SmartScout" />

        <h2 className="login-title">Login</h2>

        <form className="login-form" onSubmit={handleLogin}>

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
              />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Senha</label>
            <div className="input-wrapper">
              <span className="input-icon"><Lock/></span>
              <input
                type="password"
                className="input-base with-icon"
                placeholder="Digite sua senha"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && <p className="login-error">{error}</p>}

          <a href="#" className="forgot-password">
            <Link to="/reset-password" className="login-link">
              Esqueceu a senha?
            </Link>
          </a>

          <button
            type="submit"
            className="btn btn-primary login-button"
          >
            Entrar
          </button>

          <p className="create-account">
            Ainda não possui conta?{" "}
            <Link to="/signup" className="login-link">
              Criar conta
            </Link>
          </p>

        </form>

      </div>
    </div>
  )
}