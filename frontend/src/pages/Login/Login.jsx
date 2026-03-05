import "./Login.css"
import logo from "../../assets/logo.png"

export default function Login({ onSignUpClick }) {
  return (
    <div className="login-page bg-gradient">
      <div className="login-card">

        <img src={logo} className="login-logo" alt="SmartScout" />

        <h2 className="login-title">Login</h2>

        <form className="login-form">

          <div className="input-group">
            <label className="input-label">E-mail</label>
            <div className="input-wrapper">
              <input
                type="email"
                placeholder=""
                className="input-base"
              />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Senha</label>
            <div className="input-wrapper">
              <input
                type="password"
                placeholder=""
                className="input-base"
              />
            </div>
          </div>

          <a href="#" className="forgot-password">
            Esqueceu a senha?
          </a>

          <button className="btn btn-primary login-button">
            Entrar
          </button>

          <p className="create-account">
            Ainda não possui conta? <a href="#" onClick={(e) => { e.preventDefault(); onSignUpClick(); }} className="signup-link">Criar conta</a>
          </p>

        </form>

      </div>
    </div>
  )
}