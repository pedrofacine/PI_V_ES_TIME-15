import "./SignUp.css"
import logo from "../../assets/logo.png"
import { SyntheticEvent, useState } from "react"
import { Lock, LockKeyhole, Mail, User } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { register } from "../../services/api"

export default function SignUp() {
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSignUp = async (e: SyntheticEvent) => {
    e.preventDefault()
    setError("")
    if (!firstName.trim() || !lastName.trim() || !email.trim() || !password || !confirmPassword) {
      setError("Preencha todos os campos.")
      return
    }
    if (password.length < 8) {
      setError("A senha deve ter no mínimo 8 caracteres.")
      return
    }
    if (password !== confirmPassword) {
      setError("As senhas não coincidem.")
      return
    }

    setLoading(true)
    try {
      const data = await register({
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      })
      localStorage.setItem("token", data.access_token)
      localStorage.setItem("user", JSON.stringify(data.user))
      navigate("/", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="signup-page bg-gradient">
      <div className="white-container">

        <img src={logo} className="signup-logo" alt="SmartScout" />

        <h2 className="signup-title">Registre-se</h2>

        <form className="signup-form" onSubmit={handleSignUp}>

          <div className="signup-row">
            <div className="input-group">
              <label className="input-label">Nome</label>
              <div className="input-wrapper">
                <span className="input-icon"><User/></span> 
                <input
                  type="text"
                  placeholder="Digite seu nome"
                  className="input-base with-icon"
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
                  placeholder="Digite seu sobrenome"
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
              <span className="input-icon"><Mail/></span> 
              <input
                type="email"
                placeholder="seu-email@email.com"
                className="input-base with-icon"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="signup-row">
            <div className="input-group">
              <label className="input-label">Senha</label>
              <div className="input-wrapper">
                <span className="input-icon"><Lock/></span> 
                <input
                  type="password"
                  placeholder="Digite sua senha"
                  className="input-base with-icon"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div className="input-group">
              <label className="input-label">Confirmar Senha</label>
              <div className="input-wrapper">
                <span className="input-icon"><LockKeyhole/></span> 
                <input
                  type="password"
                  placeholder="Confirme sua senha"
                  className="input-base with-icon"
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

          {error && <p className="signup-error">{error}</p>}

          <button type="submit" className="btn btn-primary signup-button" disabled={loading}>
            {loading ? "Registrando..." : "Registrar"}
          </button>

          <p className="have-account">
            Já possui conta?{" "} 
            <Link to="/login" className="login-link">
              Entrar
            </Link>
          </p>

        </form>

      </div>
    </div>
  )
}
