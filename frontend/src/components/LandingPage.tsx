import { useState, useEffect } from 'react';
import { 
  Sparkles, 
  MessageSquare,
  ArrowRight,
  PhoneCall,
  ChevronDown
} from 'lucide-react';
import './LandingPage.css';
import bannerImg from '../assets/banner_d3a8275899.jpg';

interface LandingPageProps {
  onEnterCRM: () => void;
}

interface Message {
  id: number;
  sender: 'agent' | 'user';
  text: string;
  speaker: string;
}

export function LandingPage({ onEnterCRM }: LandingPageProps) {
  // Navigation states
  const [activeMenu, setActiveMenu] = useState<'products' | 'solutions' | null>(null);

  // Accordion state
  const [activeAccTab, setActiveAccTab] = useState<'intelligence' | 'harmony' | 'telephony'>('intelligence');

  // Interactive Voice Bot simulation state
  const [isPlayingDemo, setIsPlayingDemo] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [simStatus, setSimStatus] = useState('Idle');

  // Voicebot conversation script
  const demoConversation: Omit<Message, 'id'>[] = [
    { sender: 'agent', speaker: 'Priya (AI)', text: 'Hello! I am calling from DigiCRM. I noticed you recently requested details about our automated sales campaigns. Are you looking to implement this for support or outbound sales?' },
    { sender: 'user', speaker: 'Customer', text: 'Hi! Yes, I did. We are actually looking to automate our outbound sales qualification.' },
    { sender: 'agent', speaker: 'Priya (AI)', text: 'Excellent choice! Our AI voice agent can qualify leads and sync details directly to your CRM. I can schedule a quick 10-minute demo with our solution engineer for this Friday. How does 2:00 PM work for you?' },
    { sender: 'user', speaker: 'Customer', text: 'Friday at 2:00 PM works perfectly for me.' },
    { sender: 'agent', speaker: 'Priya (AI)', text: 'Perfect! I have scheduled your demo for Friday at 2:00 PM. A confirmation link and calendar invite have been sent to your email. Is there any specific feature you want us to cover?' },
    { sender: 'user', speaker: 'Customer', text: 'Mainly CRM integration and agent handover, please.' },
    { sender: 'agent', speaker: 'Priya (AI)', text: 'Noted! We will customize the session for you. Thank you for your time and have a great day!' }
  ];

  useEffect(() => {
    if (!isPlayingDemo) {
      setMessages([]);
      setSimStatus('Idle');
      return;
    }

    setMessages([]);
    setSimStatus('Initiating Demo Call...');
    
    let currentStep = 0;
    const timeouts: any[] = [];

    const runStep = () => {
      if (currentStep >= demoConversation.length) {
        setSimStatus('Call Completed - Site Visit Booked');
        setIsPlayingDemo(false);
        return;
      }

      const nextMsg = demoConversation[currentStep];
      setSimStatus(nextMsg.sender === 'agent' ? 'AI Speaking...' : 'Customer Speaking...');
      setMessages(prev => [...prev, { ...nextMsg, id: currentStep }]);
      currentStep++;

      const delay = nextMsg.text.length * 45;
      const timer = setTimeout(runStep, Math.max(delay, 2000));
      timeouts.push(timer);
    };

    const startTimer = setTimeout(() => {
      setSimStatus('Call Connected');
      runStep();
    }, 1500);

    timeouts.push(startTimer);

    return () => {
      timeouts.forEach(t => clearTimeout(t));
    };
  }, [isPlayingDemo]);

  const toggleDemo = () => {
    setIsPlayingDemo(prev => !prev);
  };

  return (
    <div className="landing-container" onClick={() => setActiveMenu(null)}>
      <div className="landing-bg-glow"></div>
      <div className="landing-bg-glow-2"></div>

      {/* Top Strip (Exotel Style) */}
      <div className="landing-top-strip light-strip">
        <div className="top-strip-left">
          <span>Talk to Sales:</span>
          <a href="tel:+918088919888" className="top-strip-sales-link">+91-808 8919 888</a>
        </div>
        <div className="top-strip-right">
          <span onClick={onEnterCRM}>Contact Developer</span>
          <span onClick={onEnterCRM}>Support Portal</span>
          <span onClick={onEnterCRM}>Developer Hub</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="landing-nav light-nav" onClick={e => e.stopPropagation()}>
        <div className="landing-logo">
          <PhoneCall className="crm-logo-icon" style={{ color: '#8b5cf6' }} />
          <h1>DigiCRM AI</h1>
        </div>

        <div className="landing-nav-links">
          {/* Products Dropdown Link */}
          <div 
            className={`landing-nav-item ${activeMenu === 'products' ? 'active' : ''}`}
            onMouseEnter={() => setActiveMenu('products')}
          >
            <span className="landing-nav-link">
              Products <ChevronDown size={14} />
            </span>
            {activeMenu === 'products' && (
              <div className="mega-menu">
                <div className="mega-menu-section">
                  <span className="mega-menu-title">Telephony & AI Solutions</span>
                  <div className="mega-menu-grid">
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Outbound Calling campaigns</h4>
                      <p>Bulk schedule voice campaigns to verify lead interested status.</p>
                    </div>
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Sarvam Voice Integration</h4>
                      <p>Highly lifelike Hindi & English real-time conversation flows.</p>
                    </div>
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Barge-In Takeover</h4>
                      <p>Seamless handoff from automated bot to a live human agent.</p>
                    </div>
                  </div>
                </div>
                <div className="mega-right-promo">
                  <div>
                    <h3>Exotel WebRTC Connectivity</h3>
                    <p>Telecom-grade call routing with extremely low latency. Powered by sub-300ms audio stream processing.</p>
                  </div>
                  <button className="landing-nav-btn" onClick={onEnterCRM}>Get Started</button>
                </div>
              </div>
            )}
          </div>

          {/* Solutions Dropdown Link */}
          <div 
            className={`landing-nav-item ${activeMenu === 'solutions' ? 'active' : ''}`}
            onMouseEnter={() => setActiveMenu('solutions')}
          >
            <span className="landing-nav-link">
              Solutions <ChevronDown size={14} />
            </span>
            {activeMenu === 'solutions' && (
              <div className="mega-menu">
                <div className="mega-menu-section">
                  <span className="mega-menu-title">Omnichannel Sales & Support Use Cases</span>
                  <div className="mega-menu-grid">
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Automated Appointment Scheduling</h4>
                      <p>Automatically book demos, consultations, and site visits for sales teams.</p>
                    </div>
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Instant Lead Qualification</h4>
                      <p>Pre-qualify cold digital leads across industries before handing them over to sales reps.</p>
                    </div>
                    <div className="mega-item" onClick={onEnterCRM}>
                      <h4>Customer Support Transcription</h4>
                      <p>Full transcription logs and audio storage for quality auditing and compliance.</p>
                    </div>
                  </div>
                </div>
                <div className="mega-right-promo" style={{ background: 'radial-gradient(circle at top right, rgba(59, 130, 246, 0.15), transparent)' }}>
                  <div>
                    <h3>Ready to scale?</h3>
                    <p>Deliver the premium calling & CRM experience that modern businesses expect.</p>
                  </div>
                  <button className="landing-nav-btn" onClick={onEnterCRM} style={{ background: 'var(--primary)' }}>Access Portal</button>
                </div>
              </div>
            )}
          </div>

          <span className="landing-nav-link" onClick={onEnterCRM}>Pricing</span>
          <span className="landing-nav-link" onClick={onEnterCRM}>Resources</span>
        </div>

        <button className="landing-nav-btn" onClick={onEnterCRM}>
          Enter Agent Portal
        </button>
      </nav>

      {/* Hero Carousel Section */}
      <section className="hero-slider-container light-bg">
        <div className="hero-slide slide-exotel">
          <div className="hero-content">
            <h1 className="hero-title-exotel">
              AI, agents, contact centre, network, all working as one
            </h1>
            <p className="hero-sub-desc-exotel">
              Exotel helps businesses reduce repeat contacts, increase AI containment rate, and lower cost to serve.
            </p>
            <div className="landing-hero-actions">
              <button className="btn-exotel-primary" onClick={onEnterCRM}>
                Book a Demo <ArrowRight size={18} />
              </button>
              <button className="btn-exotel-secondary" onClick={onEnterCRM}>
                Explore AI-Human Harmony
              </button>
            </div>
          </div>

          <div className="hero-image-wrapper">
            <img src={bannerImg} alt="Exotel AI-Led CX Ecosystem" className="hero-exotel-img" />
          </div>
        </div>
      </section>

      {/* Infinite Brand scroller */}
      <section className="landing-brands-section">
        <p className="brands-title">25M+ Property interactions, trusted by premium developers</p>
        <div className="brand-marquee-track">
          {Array(3).fill([
            {
              name: 'DLF',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <rect width="120" height="40" rx="4" fill="#003566"/>
                  <text x="50%" y="60%" dominantBaseline="middle" textAnchor="middle" fill="white" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="900" fontSize="16" letterSpacing="1">DLF</text>
                </svg>
              )
            },
            {
              name: 'Sobha',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <text x="15" y="25" fill="#1e3a8a" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="800" fontSize="15" letterSpacing="0.5">SOBHA</text>
                  <rect x="85" y="10" width="20" height="20" fill="#10b981" rx="2" />
                  <circle cx="95" cy="20" r="4" fill="white" />
                </svg>
              )
            },
            {
              name: 'Lodha',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <path d="M15 15 L20 25 L25 15 L30 25 L35 15" stroke="#d97706" strokeWidth="3" strokeLinecap="round" fill="none"/>
                  <text x="45" y="24" fill="#111827" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="800" fontSize="13" letterSpacing="2">LODHA</text>
                </svg>
              )
            },
            {
              name: 'Prestige',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <path d="M10 12 L25 12 L17 28 Z" fill="#ef4444"/>
                  <text x="32" y="24" fill="#ef4444" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="900" fontSize="12" letterSpacing="1">PRESTIGE</text>
                </svg>
              )
            },
            {
              name: 'Godrej',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <text x="50%" y="55%" dominantBaseline="middle" textAnchor="middle" fill="#e11d48" fontFamily="'Brush Script MT', cursive, sans-serif" fontWeight="bold" fontSize="24">Godrej</text>
                </svg>
              )
            },
            {
              name: 'Brigade',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <rect x="10" y="10" width="6" height="20" fill="#f97316" />
                  <rect x="20" y="15" width="6" height="15" fill="#eab308" />
                  <rect x="30" y="5" width="6" height="25" fill="#3b82f6" />
                  <text x="42" y="24" fill="#1e3a8a" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="800" fontSize="11" letterSpacing="1.5">BRIGADE</text>
                </svg>
              )
            },
            {
              name: 'Tata',
              element: (
                <svg viewBox="0 0 120 40" className="brand-logo-svg" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="20" cy="20" r="16" fill="#005b9f"/>
                  <path d="M20 10 L20 30 M20 10 L13 17 M20 10 L27 17" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                  <text x="45" y="24" fill="#005b9f" fontFamily="'Plus Jakarta Sans', Arial, sans-serif" fontWeight="900" fontSize="14" letterSpacing="2.5">TATA</text>
                </svg>
              )
            }
          ]).flat().map((brand, idx) => (
            <div key={idx} className="brand-logo-item">
              {brand.element}
            </div>
          ))}
        </div>
      </section>

      {/* Interactive AI Call Simulator Section */}
      <section className="simulator-section-container">
        <div className="simulator-section-header">
          <div className="landing-badge" style={{ display: 'inline-flex' }}>
            <Sparkles size={14} style={{ marginRight: '6px', display: 'inline' }} />
            Try Live Demo
          </div>
          <h2>Interactive AI Voice Bot Simulator</h2>
          <p>
            Experience how Priya, our outbound AI real estate agent, holds natural, context-aware conversations to qualify leads and book site visits in real-time.
          </p>
        </div>

        <div className="simulator-section-content">
          <div className="simulator-demo-card">
            <div className="simulator-intro-text">
              <h3>Qualified Leads in Minutes</h3>
              <p>
                Our AI voice bot integrates with your CRM to automatically call new leads, qualify their interests (budget, requirements, business size), schedule meetings, and update lead status instantly.
              </p>
              <ul className="simulator-benefits-list">
                <li><strong>90% Containment:</strong> Automated qualifying of incoming and outgoing inquiries.</li>
                <li><strong>Instant Triggering:</strong> Call leads within seconds of form submissions to boost conversions.</li>
                <li><strong>CRM Auto-logging:</strong> Instant syncing of call recordings and text transcripts.</li>
              </ul>
              <button className="btn-landing-primary" onClick={onEnterCRM} style={{ marginTop: '20px', alignSelf: 'flex-start' }}>
                Launch Agent Dashboard <ArrowRight size={18} />
              </button>
            </div>

            {/* Simulated Live Call Card */}
            <div className="landing-simulator">
              <div className="sim-header">
                <div className="sim-agent-info">
                  <div className="sim-avatar-pulse">
                    <PhoneCall size={20} className={isPlayingDemo ? 'realtime-pulse-mic' : ''} />
                  </div>
                  <div className="sim-status">
                    <h4>Outbound Sales Agent</h4>
                    <span style={{ color: isPlayingDemo ? '#10b981' : '#6b7280' }}>
                      {simStatus}
                    </span>
                  </div>
                </div>
              </div>

              <div className="sim-body">
                {messages.length === 0 ? (
                  <div className="dialer-transcript-empty">
                    <MessageSquare size={36} />
                    <p>Click "Start Call Simulator" to see Priya (AI) qualify a business lead in real-time.</p>
                  </div>
                ) : (
                  messages.map((m) => (
                    <div key={m.id} className={`sim-msg ${m.sender}`}>
                      <span className="sim-msg-label">{m.speaker}</span>
                      <div className="sim-msg-bubble">{m.text}</div>
                    </div>
                  ))
                )}
              </div>

              <div className="sim-controls">
                <button 
                  className={`btn-sim-action ${isPlayingDemo ? 'active' : ''}`}
                  onClick={toggleDemo}
                >
                  {isPlayingDemo ? 'End Demo Call' : 'Start Voice Agent Simulator'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Experience the New CX Section */}
      <section className="new-cx-section">
        <div className="new-cx-header">
          <h2>Experience the New Customer Journey</h2>
          <p>Get the best customer engagement stack built on the three pillars of Intelligence, Unity, and AI-Human Harmony.</p>
        </div>

        <div className="new-cx-grid">
          <div className="new-cx-card intelligence">
            <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/3_1_e73a05df0c.png" alt="Intelligence" className="new-cx-card-img" />
            <h3 className="new-cx-badge">INTELLIGENCE</h3>
            <p>AI-first, context-aware, and always learning. Outbound AI agents resolve customer queries and qualify customer budgets automatically.</p>
          </div>

          <div className="new-cx-card unity">
            <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/3_2_ec07dc98c8.png" alt="Unity" className="new-cx-card-img" />
            <h3 className="new-cx-badge">UNITY</h3>
            <p>One platform. One view. Frictionless lead journeys. Access call recordings, transcripts, and lead statuses inside a single CRM panel.</p>
          </div>

          <div className="new-cx-card harmony">
            <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/3_3_cec1f03438.png" alt="Harmony" className="new-cx-card-img" />
            <h3 className="new-cx-badge">HARMONY</h3>
            <p>Balance bot automation with human empathy. Supervisors can monitor live voice streams and takeover conversation handling when needed.</p>
          </div>
        </div>
      </section>

      {/* Accordion List with Dynamic Visuals */}
      <section className="accordion-section">
        <div className="acc-container">
          <div className="acc-list">
            <h2 className="gradient-text-purple" style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '40px', letterSpacing: '-0.02em' }}>
              Built for Scale, Speed, and Measurable Efficiency
            </h2>

            {/* Accordion Item 1 */}
            <div 
              className={`acc-item ${activeAccTab === 'intelligence' ? 'active' : ''}`}
              onClick={() => setActiveAccTab('intelligence')}
            >
              <div className="acc-item-header">
                <h3>Intelligence with AI & automation</h3>
              </div>
              {activeAccTab === 'intelligence' && (
                <div className="acc-item-content">
                  <p className="acc-desc">AI voice agents resolve routine customer queries, qualify buyer intent, and log transcripts automatically into the lead card.</p>
                  <ul className="acc-bullets">
                    <li>Up to 75% containment rate with AI voice and chat agents</li>
                    <li>100% conversation analysis for quality compliance</li>
                    <li>Frictionless escalation to human teams</li>
                  </ul>
                </div>
              )}
            </div>

            {/* Accordion Item 2 */}
            <div 
              className={`acc-item ${activeAccTab === 'harmony' ? 'active' : ''}`}
              onClick={() => setActiveAccTab('harmony')}
            >
              <div className="acc-item-header">
                <h3>Contact center built on AI-human harmony</h3>
              </div>
              {activeAccTab === 'harmony' && (
                <div className="acc-item-content">
                  <p className="acc-desc">Keep agents aligned with live caller transcriptions, budget analysis, and real-time guidance prompts.</p>
                  <ul className="acc-bullets">
                    <li>Up to 40% productivity gains with AI-assisted agents</li>
                    <li>Measurable reduction in repeat contacts</li>
                    <li>Shared conversational context database</li>
                  </ul>
                </div>
              )}
            </div>

            {/* Accordion Item 3 */}
            <div 
              className={`acc-item ${activeAccTab === 'telephony' ? 'active' : ''}`}
              onClick={() => setActiveAccTab('telephony')}
            >
              <div className="acc-item-header">
                <h3>Unified Communication Stack</h3>
              </div>
              {activeAccTab === 'telephony' && (
                <div className="acc-item-content">
                  <p className="acc-desc">Telecom-grade dialers powered by Exotel integration, with Webrtc calling channels and absolute data privacy.</p>
                  <ul className="acc-bullets">
                    <li>Uninterrupted engagement with unified voice & WebRTC channels</li>
                    <li>Real-time interactions with sub-300 ms stream latency</li>
                    <li>Enterprise scalability with 99.99% system uptime</li>
                  </ul>
                </div>
              )}
            </div>
          </div>
          {/* Right Column: Visual Graphic Panel */}
          <div className="acc-visual-panel" style={{ background: 'transparent', border: 'none', boxShadow: 'none' }}>
            {activeAccTab === 'intelligence' && (
              <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/4_1_18d3109c3b.png" alt="Intelligence Uptime" className="acc-visual-img" style={{ width: '100%', height: 'auto', borderRadius: '14px' }} />
            )}

            {activeAccTab === 'harmony' && (
              <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/4_2_8e23991b39.png" alt="AI Human Harmony" className="acc-visual-img" style={{ width: '100%', height: 'auto', borderRadius: '14px' }} />
            )}

            {activeAccTab === 'telephony' && (
              <img src="https://exotel-strapi-s3-bucket.s3.ap-south-1.amazonaws.com/4_3_51a8886dd8.png" alt="Unified Telephony Trunk" className="acc-visual-img" style={{ width: '100%', height: 'auto', borderRadius: '14px' }} />
            )}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="landing-cta" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.03)' }}>
        <div className="cta-box">
          <h2>Ready to Supercharge Your Business?</h2>
          <p>Get instant access to the DigiCRM portal, configure campaigns, import leads, and start automated outbound AI voice calls.</p>
          <button className="btn-landing-primary" onClick={onEnterCRM}>
            Login to CRM Portal <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <p>&copy; {new Date().getFullYear()} DigiCRM. Powered by Exotel Telephony. All rights reserved.</p>
      </footer>
    </div>
  );
}
