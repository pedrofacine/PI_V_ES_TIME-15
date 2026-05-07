import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Video,
  Target,
  Download,
  Zap,
  Eye,
  Clock,
  BarChart2,
  Shield,
  ArrowRight,
  Play,
  X,
  Mail,
  LogOut,
} from "lucide-react";
import "./LandingPage.css";
import logo from "../../assets/logo-smartscout.png";
import { isAuthenticated, getUser, clearSession } from "../../services/api";

export default function LandingPage() {
  const navigate = useNavigate();
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loggedIn = isAuthenticated();
  const user = getUser();
  const [showProfileModal, setShowProfileModal] = useState(false);

  const userName = user?.first_name && user?.last_name
    ? `${user.first_name} ${user.last_name}`
    : "Usuário";
  const userInitial = userName.charAt(0).toUpperCase();

  function handleLogout() {
    clearSession();
    setShowProfileModal(false);
    navigate(0);
  }

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add("visible");
        });
      },
      { threshold: 0.12 }
    );
    document.querySelectorAll(".fade-up").forEach((el) => {
      observerRef.current?.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <div className="landing-root">

      <nav className="landing-nav">
        <img src={logo} alt="SmartScout" className="nav-logo" />

        <ul className="nav-links">
          <li><a href="#como-funciona">Como funciona</a></li>
          <li><a href="#funcionalidades">Funcionalidades</a></li>
          <li><a href="#sobre">Sobre nós</a></li>
        </ul>

        <div className="nav-actions">
          {loggedIn ? (
            <>
              <Link to="/app" className="nav-btn-primary">
                Iniciar análise <ArrowRight size={15} />
              </Link>
              <button
                className="nav-avatar-btn"
                onClick={() => setShowProfileModal(true)}
                title="Perfil"
              >
                <div className="nav-avatar">{userInitial}</div>
              </button>
            </>
          ) : (
            <>
              <Link to="/login"  className="nav-btn-ghost">Entrar</Link>
              <Link to="/signup" className="nav-btn-primary">Criar conta</Link>
            </>
          )}
        </div>
      </nav>

      {showProfileModal && (
        <div className="landing-overlay" onClick={() => setShowProfileModal(false)}>
          <div className="landing-profile-modal" onClick={(e) => e.stopPropagation()}>
            <button className="landing-close-btn" onClick={() => setShowProfileModal(false)}>
              <X size={18} />
            </button>

            <div className="landing-profile-top">
              <div className="landing-profile-avatar">{userInitial}</div>
              <h2 className="landing-profile-name">{userName}</h2>
              <p className="landing-profile-sub">Informações da conta</p>
            </div>

            <div className="landing-profile-info">
              <div className="landing-profile-row">
                <Mail size={16} />
                <div>
                  <span className="landing-info-label">E-mail</span>
                  <strong>{user?.email}</strong>
                </div>
              </div>
            </div>

            <div className="landing-profile-actions">
              <Link to="/app" className="landing-btn-analyze" onClick={() => setShowProfileModal(false)}>
                Iniciar análise <ArrowRight size={16} />
              </Link>
              <button className="landing-btn-logout" onClick={handleLogout}>
                <LogOut size={16} /> Sair da conta
              </button>
              <button className="landing-btn-close" onClick={() => setShowProfileModal(false)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      <section className="hero">
        <div className="hero-bg">
          <div className="hero-grid" />
        </div>

        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            Análise de vídeo com Inteligência Artificial
          </div>

          <h1 className="hero-title">
            Recorte automático{" "}
            <span className="hero-title-gradient">de lances</span>{" "}
            do seu jogador
          </h1>

          <p className="hero-subtitle">
            Envie um vídeo de partida, selecione o atleta e o SmartScout entrega
            automaticamente todos os momentos em que ele participou — sem trabalho manual.
          </p>

          <div className="hero-actions">
            {loggedIn ? (
              <Link to="/app" className="hero-btn-primary">
                Iniciar análise <ArrowRight size={18} />
              </Link>
            ) : (
              <>
                <Link to="/signup" className="hero-btn-primary">
                  Começar gratuitamente <ArrowRight size={18} />
                </Link>
                <a href="#como-funciona" className="hero-btn-ghost">
                  <Play size={16} style={{ marginRight: "0.4rem" }} />
                  Ver como funciona
                </a>
              </>
            )}
          </div>
        </div>

        <div className="hero-scroll-hint">
          <div className="scroll-mouse">
            <div className="scroll-wheel" />
          </div>
          <span>Role para baixo</span>
        </div>
      </section>

      <div className="stats-bar">
        <div className="stats-inner">
          <div className="stat-item">
            <div className="stat-number">95%</div>
            <div className="stat-label">Precisão na detecção</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">10×</div>
            <div className="stat-label">Mais rápido que edição manual</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">100%</div>
            <div className="stat-label">Automatizado com IA</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">+500</div>
            <div className="stat-label">Vídeos analisados</div>
          </div>
        </div>
      </div>

      <div className="how-it-works" id="como-funciona">
        <div className="section">
          <div className="fade-up">
            <p className="section-label">Como funciona</p>
            <h2 className="section-title">Três passos para ter seus clipes</h2>
            <p className="section-desc">
              Em menos de alguns minutos você tem todos os lances do atleta
              selecionado, prontos para download.
            </p>
          </div>

          <div className="steps-grid">
            <div className="step-card fade-up">
              <div className="step-number">01</div>
              <div className="step-icon"><Video size={22} /></div>
              <h3 className="step-title">Envie o vídeo</h3>
              <p className="step-desc">
                Faça upload do vídeo da partida diretamente na plataforma.
                Suportamos os principais formatos de vídeo.
              </p>
            </div>
            <div className="step-card fade-up" style={{ transitionDelay: "0.1s" }}>
              <div className="step-number">02</div>
              <div className="step-icon"><Target size={22} /></div>
              <h3 className="step-title">Selecione o jogador</h3>
              <p className="step-desc">
                Informe o número da camisa do atleta. Nossa IA rastreia
                a movimentação dele durante toda a partida.
              </p>
            </div>
            <div className="step-card fade-up" style={{ transitionDelay: "0.2s" }}>
              <div className="step-number">03</div>
              <div className="step-icon"><Download size={22} /></div>
              <h3 className="step-title">Baixe os clipes</h3>
              <p className="step-desc">
                Receba automaticamente todos os recortes com os lances
                do jogador selecionado, organizados e prontos para uso.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div id="funcionalidades">
        <div className="section">
          <div className="fade-up">
            <p className="section-label">Funcionalidades</p>
            <h2 className="section-title">Tudo que você precisa em um só lugar</h2>
            <p className="section-desc">
              Ferramentas desenvolvidas para analistas, treinadores e scouts
              que precisam de agilidade e precisão.
            </p>
          </div>

          <div className="features-grid">
            <div className="feature-card fade-up">
              <div className="feature-icon"><Zap size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Detecção em tempo real</h4>
                <p className="feature-desc">Acompanhe o progresso ao vivo, com os clipes aparecendo conforme são gerados.</p>
              </div>
            </div>
            <div className="feature-card fade-up" style={{ transitionDelay: "0.05s" }}>
              <div className="feature-icon"><Eye size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Rastreamento por número</h4>
                <p className="feature-desc">Identifica o jogador pela camisa. Basta informar o número e a IA faz o resto.</p>
              </div>
            </div>
            <div className="feature-card fade-up" style={{ transitionDelay: "0.1s" }}>
              <div className="feature-icon"><Clock size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Corte de vídeo preciso</h4>
                <p className="feature-desc">Defina o trecho exato da partida com nosso controle de corte por tempo interativo.</p>
              </div>
            </div>
            <div className="feature-card fade-up" style={{ transitionDelay: "0.15s" }}>
              <div className="feature-icon"><BarChart2 size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Histórico de análises</h4>
                <p className="feature-desc">Todos os seus clipes ficam salvos e organizados por data por até 14 dias.</p>
              </div>
            </div>
            <div className="feature-card fade-up" style={{ transitionDelay: "0.2s" }}>
              <div className="feature-icon"><Shield size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Conta segura</h4>
                <p className="feature-desc">Seus vídeos e clipes ficam protegidos na sua conta com autenticação JWT.</p>
              </div>
            </div>
            <div className="feature-card fade-up" style={{ transitionDelay: "0.25s" }}>
              <div className="feature-icon"><Download size={22} /></div>
              <div className="feature-body">
                <h4 className="feature-title">Download em lote</h4>
                <p className="feature-desc">Baixe todos os clipes de uma análise com um único clique.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="about-section" id="sobre">
        <div className="section">
          <div className="about-inner">
            <div className="fade-up">
              <p className="section-label">Sobre nós</p>
              <h2 className="section-title">Tecnologia a serviço do esporte</h2>
              <p className="section-desc" style={{ marginBottom: "1.5rem" }}>
                O SmartScout nasceu da necessidade real de analistas e treinadores
                que perdiam horas editando vídeos manualmente para extrair lances de jogadores específicos.
              </p>
              <p className="section-desc" style={{ marginBottom: "1.5rem" }}>
                Desenvolvemos uma solução que combina visão computacional e inteligência artificial
                para automatizar completamente esse processo, devolvendo tempo valioso para quem
                realmente importa: o trabalho de análise e desenvolvimento dos atletas.
              </p>
              <p className="section-desc">
                Somos um time apaixonado por esporte e tecnologia, comprometidos em entregar
                uma ferramenta simples, rápida e confiável.
              </p>
            </div>

            <div className="about-visual fade-up" style={{ transitionDelay: "0.15s" }}>
              <div className="about-card-main">
                <img src={logo} alt="SmartScout" className="about-logo" />
                <h3 className="about-card-title">SmartScout</h3>
                <p className="about-card-text">
                  Análise inteligente de vídeos esportivos. Desenvolvido para tornar o trabalho
                  de analistas e treinadores mais eficiente com o poder da Inteligência Artificial.
                </p>
                <div className="about-tags">
                  <span className="about-tag">Visão Computacional</span>
                  <span className="about-tag">Inteligência Artificial</span>
                  <span className="about-tag">Análise Esportiva</span>
                  <span className="about-tag">FastAPI</span>
                  <span className="about-tag">React</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <section className="cta-section">
        <h2 className="cta-title fade-up">
          {loggedIn ? "Continue sua análise" : "Pronto para economizar horas de edição?"}
        </h2>
        <p className="cta-desc fade-up">
          {loggedIn
            ? "Acesse a plataforma e inicie uma nova análise agora mesmo."
            : "Crie sua conta gratuitamente e comece a analisar seus vídeos agora mesmo."}
        </p>
        <div className="cta-actions fade-up">
          {loggedIn ? (
            <Link to="/app" className="hero-btn-primary">
              Iniciar análise <ArrowRight size={18} />
            </Link>
          ) : (
            <>
              <Link to="/signup" className="hero-btn-primary">
                Criar conta grátis <ArrowRight size={18} />
              </Link>
              <Link to="/login" className="hero-btn-ghost">
                Já tenho conta
              </Link>
            </>
          )}
        </div>
      </section>

      <footer className="footer">
        <div className="footer-inner">
          <img src={logo} alt="SmartScout" className="footer-logo" />
          <ul className="footer-links">
            <li><a href="#como-funciona">Como funciona</a></li>
            <li><a href="#funcionalidades">Funcionalidades</a></li>
            <li><a href="#sobre">Sobre nós</a></li>
            <li><a href="mailto:contato@smartscout.com">Contato</a></li>
          </ul>
          <span className="footer-copy">
            © {new Date().getFullYear()} SmartScout. Todos os direitos reservados.
          </span>
        </div>
      </footer>

    </div>
  );
}
